Outline of Tarpaulin Course Management:

1. Imports and Initial Setup
   - flask: Flask, request, jsonify, send_file
   - google.cloud: datastore, storage
   - requests, json
   - jose.jwt, urllib for Auth0 JWT verification
   - authlib OAuth setup for Auth0
   - io for serving avatar files

2. Application Configuration
   - Initialize Flask app and secret key
   - Initialize Datastore client
   - Initialize Storage client and specify avatar bucket name
   - Define Auth0-related constants (CLIENT_ID, CLIENT_SECRET, DOMAIN, ALGORITHMS)

3. OAuth and AuthError Classes
   - Register Auth0 with authlib
   - Define AuthError exception class
   - Register error handler for AuthError

4. Helper Functions
   a. verify_jwt(request)
      - Extract Bearer token, fetch JWKS, verify JWT signature and claims
      - Return decoded payload
   b. get_user_by_sub(sub)
      - Query Datastore 'users' kind for entity with matching 'sub'
      - Return user entity or None
   c. get_user_by_id(user_id)
      - Retrieve a Datastore 'users' entity by numeric ID
      - Return user entity or None
   d. require_auth_and_get_user(request)
      - Call verify_jwt to get payload
      - Extract 'sub' from payload and fetch corresponding user entity
      - If no matching user, raise AuthError(403)
      - Return (payload, user_entity)
   e. check_admin(user_entity)
      - If user_entity['role'] != 'admin', raise AuthError(403)
   f. check_owner_or_admin(payload, user_entity, target_user_id)
      - If payload['sub'] matches user_entity['sub'] && IDs match, allow
      - Else if user_entity['role'] == 'admin', allow
      - Else raise AuthError(403)
   g. check_owner(payload, user_entity, target_user_id)
      - If payload['sub'] matches user_entity['sub'] && IDs match, allow
      - Else raise AuthError(403)
   h. get_course_by_id(course_id)
      - Retrieve 'courses' entity by numeric ID
      - Return course entity or None

5. Endpoint Implementations

   1. POST /users/login
      - Expect JSON with 'username' and 'password'
      - Call Auth0 /oauth/token endpoint to get JWT
      - Return JSON { "token": "<JWT>" } or 400/401 as specified

   2. GET /users
      - require_auth_and_get_user -> get calling user entity
      - check_admin on calling user
      - Query all 'users' entities in Datastore
      - For each user, collect { "id": id, "role": role, "sub": sub }
      - Return list

   3. GET /users/<user_id>
      - require_auth_and_get_user -> get calling user entity
      - Retrieve target_user via get_user_by_id
      - If not found, raise AuthError(403)
      - check_owner_or_admin to allow if caller is admin or same user
      - Build response:
        - Always include "id", "role", "sub"
        - If user has avatar in GCS (check_blob_exists), add "avatar_url": f"/users/{id}/avatar"
        - If role in ["instructor", "student"], include "courses": []
          - For instructor: query 'courses' where instructor_id == user_id, build URL list
          - For student: query 'courses' where user_id in course['students'] list, build URL list
      - Return JSON

   4. POST /users/<user_id>/avatar
      - require_auth_and_get_user -> get calling user entity
      - check_owner to allow only user themselves
      - Validate 'file' in request.files; if missing, return 400
      - Ensure file extension == '.png'
      - Upload to GCS bucket under object name "avatars/{user_id}.png"
      - On success, return { "avatar_url": f"/users/{user_id}/avatar" }

   5. GET /users/<user_id>/avatar
      - require_auth_and_get_user -> get calling user entity
      - check_owner to allow only user
      - Build blob name "avatars/{user_id}.png", check if exists in GCS; if not, return 404
      - Download blob into memory and send as response with correct mimetype

   6. DELETE /users/<user_id>/avatar
      - require_auth_and_get_user -> get calling user entity
      - check_owner to allow only user
      - Check if blob exists; if not, return 404
      - Delete blob; return 204

   7. POST /courses
      - require_auth_and_get_user -> get calling user entity
      - check_admin on calling user
      - Parse JSON body; verify required fields: subject, number, title, term, instructor_id
      - Verify instructor_id corresponds to an existing user_entity with role 'instructor'; if not, return 400
      - Create new Datastore entity in 'courses' kind with properties:
        subject, number, title, term, instructor_id, students=[] (empty list)
      - Put into Datastore, get assigned ID
      - Build response JSON with all properties including "id" and "self": f"/courses/{id}"
      - Return 201

   8. GET /courses
      - Parse optional query params offset and limit; default offset=0, limit=3
      - Query 'courses' kind, order by 'subject', apply offset and limit
      - Build list of course dicts: id, instructor_id, number, title, term, subject, self URL
      - If more courses beyond current page, build "next" link with updated offset
      - Return JSON { "courses": [...], "next": "<url>" } or omit 'next' if last page

   9. GET /courses/<course_id>
      - Retrieve course via get_course_by_id; if not found, return 404
      - Build response dict same as in POST /courses response
      - Return 200

   10. PATCH /courses/<course_id>
       - require_auth_and_get_user -> get calling user entity
       - check_admin on calling user
       - Retrieve course; if not found, return 403
       - Parse JSON body; if 'instructor_id' in body, verify it corresponds to a user role 'instructor'; else return 400
       - Update only provided fields in the course entity
       - Save entity; build response dict and return 200

   11. DELETE /courses/<course_id>
       - require_auth_and_get_user -> get calling user entity
       - check_admin on calling user
       - Retrieve course; if not found, return 403
       - Delete course entity
       - Return 204

   12. PATCH /courses/<course_id>/students
       - require_auth_and_get_user -> get calling user entity
       - Retrieve course; if not found, return 403
       - If calling user is not admin and not course instructor, raise 403
       - Parse JSON body: arrays 'add', 'remove'
       - Check for intersection between 'add' and 'remove'; if any, return 409
       - For each ID in 'add' and 'remove', verify user exists and role == 'student'; else return 409
       - Modify course['students'] array accordingly:
         - For each student_id in 'add': if not already in list, append
         - For each student_id in 'remove': if in list, remove
       - Save course entity; return 200 with empty body

   13. GET /courses/<course_id>/students
       - require_auth_and_get_user -> get calling user entity
       - Retrieve course; if not found, return 403
       - If calling user is not admin and not course instructor, raise 403
       - Return JSON list of student IDs (course['students'] or empty list)

6. Running the Application
   - app.run(host='127.0.0.1', port=8080, debug=True)