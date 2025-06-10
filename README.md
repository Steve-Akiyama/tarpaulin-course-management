
# Tarpaulin Course Management Tool

A fully RESTful API for managing courses, students, and instructors, built using Python 3 and the Google Cloud Platform. It is secured with Auth0 authentication and designed to demonstrate secure, scalable cloud-native development practices.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Setup Instructions](#setup-instructions)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Deployment](#deployment)
- [Notes](#notes)

---

## Overview

Tarpaulin is a backend-only course management system where:
- Authenticated users (instructors) can manage courses.
- Students can be created and assigned to courses.
- Admins have additional privileges like listing or removing any user.
- JSON is the primary data format for input/output.

This project was created for CS493 at Oregon State University and graded via Postman scripts using Newman.

---

## Features

- 🔐 **Auth0 Authentication** (JWT-based)
- 🧑‍🏫 Role-based access control (admin, instructor)
- 📚 Course management (CRUD)
- 👨‍🎓 Student management (CRUD)
- 🗂️ Assign/unassign students to courses
- ☁️ Hosted on Google Cloud App Engine
- 🧪 Tested with Postman/Newman

---

## Tech Stack

- **Backend**: Python 3.11 (Flask)
- **Auth**: Auth0
- **Database**: Google Cloud Datastore
- **File Storage**: Google Cloud Storage
- **Hosting**: Google App Engine (Standard Environment)

---

## Setup Instructions

### 1. Clone the Repo

```bash
git clone https://github.com/yourusername/tarpaulin-course-management.git
cd tarpaulin-course-management
```
2. Set Up Virtual Environment
```bash
python3 -m venv env
source env/bin/activate  # Windows: env\Scripts\activate
pip install -r requirements.txt
```
3. Set Environment Variables
```bash
Create a .env file or export the following:

export AUTH0_DOMAIN=your-auth0-domain
export API_AUDIENCE=your-api-audience
export CLIENT_ID=...
export CLIENT_SECRET=...
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```
4. Enable Required GCP Services

- App Engine

- Datastore

- Cloud Storage

Create a bucket if needed:
```bash
gsutil mb -p your-gcp-project-id gs://your-bucket-name/
```
---

## Authentication

This API uses Auth0 for secure access control. Each request must include a valid JWT in the Authorization header:

Authorization: Bearer <JWT>

Roles supported:

- **Admin**: Has full control over all resources.
- **Instructor**: Can create/manage their own courses and students.
- **Student**: Can be enrolled in a course, change their avatar & person details.

Tokens are expected to be provided via Postman tests or through Auth0 logins.

---
## API Endpoints

| Resource | Endpoint | Methods |
| -------- | -------- | ------- |
| Users	   | /users	  | GET (admin) |
|          |/users/\<**id**>|	GET, DELETE|
|Courses|	/courses|	GET, POST|
|					 |	/courses/\<**id**>|	GET, PATCH, DELETE|
|Students	 |/students	|GET, POST|
|          |/students/\<**id**>|	GET, PATCH, DELETE|
|          |/students/\<**id**>/courses/<cid>|	PUT, DELETE|


Note: Only course owners (instructors) can modify their own course and student data.

---
## Testing
#### Preloaded Users
```bash
9 users (6 instructors, 3 admins) are preloaded via seed.py into both Auth0 and Datastore.
```
#### Running Postman Tests

The project includes a .postman_collection.json and .postman_environment.json file.

To run the tests:

```bash
newman run TarpaulinCollection.postman_collection.json -e TarpaulinEnvironment.postman_environment.json
```

Tests will verify:
```bash
Status codes

Auth enforcement

Role enforcement

Correct data response

JWT decoding with get_sub() helper
 ```


---
## Deployment
1. Deploy to App Engine
```bash
gcloud app deploy
```
2. Make sure app.yaml is configured properly (runtime, env variables, etc.).
## Notes

- JWT parsing is performed server-side to verify user identity and roles.

- All endpoints return 406 Not Acceptable if a client requests non-JSON formats.

- API strictly enforces ownership: instructors can only access/manipulate their own data.

- Users are tracked both in Auth0 (for auth) and in Datastore (for course ownership checks).

License

MIT © 2025 Steve Akiyama
