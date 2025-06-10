import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file, url_for
from google.cloud import datastore, storage
import requests
import json
from io import BytesIO
from six.moves.urllib.request import urlopen
from jose import jwt
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'

# Initialize Datastore and Storage clients
datastore_client = datastore.Client()
storage_client = storage.Client()

# Load environment variables
load_dotenv()

AVATAR_BUCKET = os.getenv('AVATAR_BUCKET')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
DOMAIN = os.getenv('DOMAIN')

ALGORITHMS = ["RS256"]

# OAuth registration for Auth0
oauth = OAuth(app)
auth0 = oauth.register(
    'auth0',
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    api_base_url=f"https://{DOMAIN}",
    access_token_url=f"https://{DOMAIN}/oauth/token",
    authorize_url=f"https://{DOMAIN}/authorize",
    client_kwargs={'scope': 'openid profile email'},
)

# Datastore kind names
USERS_KIND = 'users'
COURSES_KIND = 'courses'


# AuthError exception for JWT issues
class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


def verify_jwt(request):
    """
    Verify JWT in Authorization header using Auth0 JWKS.
    Returns decoded payload on success; raises AuthError on failure.
    """
    auth_header = request.headers.get('Authorization', None)
    if not auth_header:
        raise AuthError({"Error": "Unauthorized"}, 401)

    parts = auth_header.split()
    if parts[0].lower() != 'bearer' or len(parts) != 2:
        raise AuthError({"Error": "Unauthorized"}, 401)

    token = parts[1]
    jsonurl = urlopen(f"https://{DOMAIN}/.well-known/jwks.json")
    jwks = json.loads(jsonurl.read())

    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError:
        raise AuthError({"Error": "Unauthorized"}, 401)

    if unverified_header.get("alg") != "RS256":
        raise AuthError({"Error": "Unauthorized"}, 401)

    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if not rsa_key:
        raise AuthError({"Error": "Unauthorized"}, 401)

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=CLIENT_ID,
            issuer=f"https://{DOMAIN}/"
        )
    except jwt.ExpiredSignatureError:
        raise AuthError({"Error": "Unauthorized"}, 401)
    except jwt.JWTClaimsError:
        raise AuthError({"Error": "Unauthorized"}, 401)
    except Exception:
        raise AuthError({"Error": "Unauthorized"}, 401)

    print("JWT payload:", payload)
    return payload


def get_user_by_sub(sub):
    """
    Query Datastore 'users' for an entity with the given Auth0 subject.
    Return the entity or None.
    """
    query = datastore_client.query(kind=USERS_KIND)
    query.add_filter('sub', '=', sub)
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def get_user_by_id(user_id):
    """
    Retrieve Datastore 'users' entity by numeric ID.
    Return the entity or None.
    """
    key = datastore_client.key(USERS_KIND, int(user_id))
    user = datastore_client.get(key)
    return user


def require_auth_and_get_user(request):
    """
    Verify JWT and fetch corresponding user entity from Datastore.
    Returns (payload, user_entity).
    Raises AuthError if JWT invalid or no matching user.
    """
    payload = verify_jwt(request)
    sub = payload.get('sub')
    user = get_user_by_sub(sub)
    if not user:
        raise AuthError({"Error": "Unauthorized"}, 403)
    return payload, user


def check_admin(user_entity):
    """
    Ensure user_entity['role'] == 'admin'; else raise AuthError(403).
    """
    if user_entity.get('role') != 'admin':
        raise AuthError({"Error": "You don't have permission on this resource"}, 403)


def check_owner_or_admin(payload, calling_user, target_user_id):
    """
    Allow if calling_user is admin OR payload['sub'] corresponds to target_user_id.
    Else raise AuthError(403).
    """
    if calling_user.get('role') == 'admin':
        return
    if calling_user.key.id != int(target_user_id):
        raise AuthError({"Error": "You don't have permission on this resource"}, 403)


def check_owner(payload, calling_user, target_user_id):
    """
    Allow only if payload['sub'] matches calling_user and calling_user.id == target_user_id.
    Else raise AuthError(403).
    """
    if calling_user.key.id != int(target_user_id):
        raise AuthError({"Error": "You don't have permission on this resource"}, 403)


def get_course_by_id(course_id):
    """
    Retrieve Datastore 'courses' entity by numeric ID.
    Return the entity or None.
    """
    key = datastore_client.key(COURSES_KIND, int(course_id))
    course = datastore_client.get(key)
    return course


def check_blob_exists(bucket_name, blob_name):
    """
    Check if a blob exists in the given GCS bucket.
    """
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.exists()

@app.route('/')
def hello_world():
    return "Hello, World! This is the Tarpaulin API, written by saakiyama02@gmail.com."

@app.route('/users/login', methods=['POST'])
def login_user():
    """
    POST /users/login
    Request JSON: { "username": "...", "password": "..." }
    Response: { "token": "<JWT>" } or 400/401
    """
    content = request.get_json()
    if not content or 'username' not in content or 'password' not in content:
        return jsonify({"Error": "The request body is invalid"}), 400

    username = content['username']
    password = content['password']
    body = {
        'grant_type': 'password',
        'username': username,
        'password': password,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': 'openid'  # Request id_token
    }
    headers = {'content-type': 'application/json'}
    url = f'https://{DOMAIN}/oauth/token'
    r = requests.post(url, json=body, headers=headers)

    if r.status_code == 200:
        token_response = r.json()
        if 'id_token' in token_response:  # Use id_token (JWT) instead of access_token
            return jsonify({"token": token_response['id_token']}), 200
        else:
            return jsonify({"Error": "Unauthorized"}), 401
    elif r.status_code == 400:
        return jsonify({"Error": "The request body is invalid"}), 400
    else:
        return jsonify({"Error": "Unauthorized"}), 401


@app.route('/users', methods=['GET'])
def get_all_users():
    """
    GET /users
    Admin only. Returns list of all users: [ { id, role, sub }, ... ]
    """
    payload, calling_user = require_auth_and_get_user(request)
    check_admin(calling_user)

    query = datastore_client.query(kind=USERS_KIND)
    users = list(query.fetch())
    response = []
    for u in users:
        response.append({
            "id": u.key.id,
            "role": u.get('role'),
            "sub": u.get('sub')
        })
    return jsonify(response), 200


@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """
    GET /users/<user_id>
    Admin or user themselves. Returns user details with optional avatar_url and courses.
    """
    payload, calling_user = require_auth_and_get_user(request)
    target_user = get_user_by_id(user_id)
    if not target_user:
        raise AuthError({"Error": "Not found"}, 403)

    check_owner_or_admin(payload, calling_user, user_id)

    response = {
        "id": target_user.key.id,
        "role": target_user.get('role'),
        "sub": target_user.get('sub')
    }

    # Check and include avatar_url if exists
    blob_name = f"avatars/{user_id}.png"
    if check_blob_exists(AVATAR_BUCKET, blob_name):
        avatar_url = url_for('get_user_avatar', user_id=user_id, _external=True)
        response['avatar_url'] = avatar_url

    # Include courses if role is instructor or student
    role = target_user.get('role')
    if role in ['instructor', 'student']:
        courses_list = []
        if role == 'instructor':
            # Query courses where instructor_id == user_id
            query = datastore_client.query(kind=COURSES_KIND)
            query.add_filter('instructor_id', '=', int(user_id))
            for c in query.fetch():
                courses_list.append(url_for('get_course', course_id=c.key.id, _external=True))
        else:  # student
            # Query all courses and include those where user_id in course['students']
            query = datastore_client.query(kind=COURSES_KIND)
            for c in query.fetch():
                students = c.get('students', [])
                if int(user_id) in students:
                    courses_list.append(url_for('get_course', course_id=c.key.id, _external=True))
        response['courses'] = courses_list

    return jsonify(response), 200


@app.route('/users/<user_id>/avatar', methods=['POST'])
def create_or_update_avatar(user_id):
    """
    POST /users/<user_id>/avatar
    Owner only. Uploads or updates user's avatar (.png) to GCS.
    """
    payload, calling_user = require_auth_and_get_user(request)
    # user must be owner
    check_owner(payload, calling_user, user_id)

    if 'file' not in request.files:
        return jsonify({"Error": "The request body is invalid"}), 400

    file = request.files['file']
    if not file.filename.lower().endswith('.png'):
        return jsonify({"Error": "The request body is invalid"}), 400

    blob_name = f"avatars/{user_id}.png"
    bucket = storage_client.bucket(AVATAR_BUCKET)
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file, content_type='image/png')

    avatar_url = url_for('get_user_avatar', user_id=user_id, _external=True)
    return jsonify({"avatar_url": avatar_url}), 200


@app.route('/users/<user_id>/avatar', methods=['GET'])
def get_user_avatar(user_id):
    """
    GET /users/<user_id>/avatar
    Owner only. Returns avatar file or 404 if not exists.
    """
    payload, calling_user = require_auth_and_get_user(request)
    check_owner(payload, calling_user, user_id)

    blob_name = f"avatars/{user_id}.png"
    bucket = storage_client.bucket(AVATAR_BUCKET)
    blob = bucket.blob(blob_name)
    if not blob.exists():
        return jsonify({"Error": "Not found"}), 404

    img_bytes = blob.download_as_bytes()
    return send_file(
        BytesIO(img_bytes),
        mimetype='image/png',
        as_attachment=False,
        attachment_filename=f"{user_id}.png"
    ), 200


@app.route('/users/<user_id>/avatar', methods=['DELETE'])
def delete_user_avatar(user_id):
    """
    DELETE /users/<user_id>/avatar
    Owner only. Deletes avatar or 404 if not exists.
    """
    payload, calling_user = require_auth_and_get_user(request)
    check_owner(payload, calling_user, user_id)

    blob_name = f"avatars/{user_id}.png"
    bucket = storage_client.bucket(AVATAR_BUCKET)
    blob = bucket.blob(blob_name)
    if not blob.exists():
        return jsonify({"Error": "Not found"}), 404

    blob.delete()
    return '', 204


@app.route('/courses', methods=['POST'])
def create_course():
    """
    POST /courses
    Admin only. Create a course.
    Request JSON: subject, number, title, term, instructor_id
    """
    payload, calling_user = require_auth_and_get_user(request)
    check_admin(calling_user)

    content = request.get_json()
    required_fields = ['subject', 'number', 'title', 'term', 'instructor_id']
    if not content or not all(field in content for field in required_fields):
        return jsonify({"Error": "The request body is invalid"}), 400

    instructor_id = content['instructor_id']
    instructor = get_user_by_id(instructor_id)
    if not instructor or instructor.get('role') != 'instructor':
        return jsonify({"Error": "The request body is invalid"}), 400

    new_course_key = datastore_client.key(COURSES_KIND)
    new_course = datastore.Entity(key=new_course_key)
    new_course.update({
        "subject": content['subject'],
        "number": content['number'],
        "title": content['title'],
        "term": content['term'],
        "instructor_id": int(instructor_id),
        "students": []
    })
    datastore_client.put(new_course)

    course_id = new_course.key.id
    response_body = {
        "id": course_id,
        "instructor_id": new_course['instructor_id'],
        "number": new_course['number'],
        "self": url_for('get_course', course_id=course_id, _external=True),
        "subject": new_course['subject'],
        "term": new_course['term'],
        "title": new_course['title']
    }
    return jsonify(response_body), 201


@app.route('/courses', methods=['GET'])
def get_all_courses():
    """
    GET /courses
    Unprotected. Paginated by offset & limit (limit=3), sorted by subject.
    """
    # Default pagination parameters
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 3))
    except ValueError:
        return jsonify({"Error": "The request body is invalid"}), 400

    query = datastore_client.query(kind=COURSES_KIND)
    query.order = ['subject']
    courses = list(query.fetch(offset=offset, limit=limit + 1))  # fetch one extra to check next

    response_courses = []
    for idx, c in enumerate(courses[:limit]):
        response_courses.append({
            "id": c.key.id,
            "instructor_id": c.get('instructor_id'),
            "number": c.get('number'),
            "self": url_for('get_course', course_id=c.key.id, _external=True),
            "subject": c.get('subject'),
            "term": c.get('term'),
            "title": c.get('title')
        })

    response_body = {"courses": response_courses}
    # If there's an extra entry beyond limit, build next link
    if len(courses) > limit:
        next_offset = offset + limit
        next_url = url_for('get_all_courses', offset=next_offset, limit=limit, _external=True)
        response_body['next'] = next_url

    return jsonify(response_body), 200


@app.route('/courses/<course_id>', methods=['GET'])
def get_course(course_id):
    """
    GET /courses/<course_id>
    Unprotected. Return course info or 404.
    """
    course = get_course_by_id(course_id)
    if not course:
        return jsonify({"Error": "Not found"}), 404

    response_body = {
        "id": course.key.id,
        "instructor_id": course.get('instructor_id'),
        "number": course.get('number'),
        "self": url_for('get_course', course_id=course.key.id, _external=True),
        "subject": course.get('subject'),
        "term": course.get('term'),
        "title": course.get('title')
    }
    return jsonify(response_body), 200


@app.route('/courses/<course_id>', methods=['PATCH'])
def update_course(course_id):
    """
    PATCH /courses/<course_id>
    Admin only. Partial update. Validate instructor_id if provided.
    """
    payload, calling_user = require_auth_and_get_user(request)
    check_admin(calling_user)

    course = get_course_by_id(course_id)
    if not course:
        raise AuthError({"Error": "Not found"}, 403)

    content = request.get_json()
    # Validate instructor_id if present
    if 'instructor_id' in content:
        new_instructor = get_user_by_id(content['instructor_id'])
        if not new_instructor or new_instructor.get('role') != 'instructor':
            return jsonify({"Error": "The request body is invalid"}), 400
        course['instructor_id'] = int(content['instructor_id'])

    # Update other fields if present
    for field in ['subject', 'number', 'title', 'term']:
        if field in content:
            course[field] = content[field]

    datastore_client.put(course)

    response_body = {
        "id": course.key.id,
        "instructor_id": course.get('instructor_id'),
        "number": course.get('number'),
        "self": url_for('get_course', course_id=course.key.id, _external=True),
        "subject": course.get('subject'),
        "term": course.get('term'),
        "title": course.get('title')
    }
    return jsonify(response_body), 200


@app.route('/courses/<course_id>', methods=['DELETE'])
def delete_course(course_id):
    """
    DELETE /courses/<course_id>
    Admin only. Delete course and associated enrollment.
    """
    payload, calling_user = require_auth_and_get_user(request)
    check_admin(calling_user)

    course = get_course_by_id(course_id)
    if not course:
        raise AuthError({"Error": "Not found"}, 403)

    # Delete course entity
    datastore_client.delete(course.key)
    return '', 204


@app.route('/courses/<course_id>/students', methods=['PATCH'])
def update_course_enrollment(course_id):
    """
    PATCH /courses/<course_id>/students
    Admin or course instructor. Modify enrollment.
    Request JSON: { "add": [ids], "remove": [ids] }
    """
    payload, calling_user = require_auth_and_get_user(request)
    course = get_course_by_id(course_id)
    if not course:
        raise AuthError({"Error": "Not found"}, 403)

    # Check permissions: admin or course instructor
    if calling_user.get('role') != 'admin' and course.get('instructor_id') != calling_user.key.id:
        raise AuthError({"Error": "You don't have permission on this resource"}, 403)

    content = request.get_json()
    if not content or 'add' not in content or 'remove' not in content:
        return jsonify({"Error": "The request body is invalid"}), 400

    add_list = content.get('add', [])
    remove_list = content.get('remove', [])

    # Check for intersection
    intersection = set(add_list).intersection(set(remove_list))
    if intersection:
        return jsonify({"Error": "Enrollment data is invalid"}), 409

    # Validate all IDs in add_list and remove_list are existing students
    for sid in set(add_list + remove_list):
        student = get_user_by_id(sid)
        if not student or student.get('role') != 'student':
            return jsonify({"Error": "Enrollment data is invalid"}), 409

    current_students = set(course.get('students', []))
    # Add students
    for sid in add_list:
        current_students.add(int(sid))
    # Remove students
    for sid in remove_list:
        current_students.discard(int(sid))

    course['students'] = list(current_students)
    datastore_client.put(course)
    return '', 200


@app.route('/courses/<course_id>/students', methods=['GET'])
def get_course_enrollment(course_id):
    """
    GET /courses/<course_id>/students
    Admin or course instructor. Return list of student IDs.
    """
    payload, calling_user = require_auth_and_get_user(request)
    course = get_course_by_id(course_id)
    if not course:
        raise AuthError({"Error": "Not found"}, 403)

    # Check permissions
    if calling_user.get('role') != 'admin' and course.get('instructor_id') != calling_user.key.id:
        raise AuthError({"Error": "You don't have permission on this resource"}, 403)

    students = course.get('students', [])
    return jsonify(students), 200


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
