# seed_users.py
from google.cloud import datastore
import os
from dotenv import load_dotenv

# Load .env so GOOGLE_APPLICATION_CREDENTIALS works
load_dotenv()

datastore_client = datastore.Client()
USERS_KIND = 'users'

# List of users from your Auth0 dashboard
users_to_create = [
    { "sub": "auth0|684297df8d0f406b0f06d505", "role": "admin" },  # admin1@osu.com

    { "sub": "auth0|684298498d0f406b0f06d50b", "role": "instructor" },  # instructor1@osu.com
    { "sub": "auth0|684298be96a28901c3b1f730", "role": "instructor" },  # instructor2@osu.com

    { "sub": "auth0|684298fe8d0f406b0f06d520", "role": "student" },    # student1@osu.com
    { "sub": "auth0|6842991d8d0f406b0f06d524", "role": "student" },    # student2@osu.com
    { "sub": "auth0|6842992d96a28901c3b1f73b", "role": "student" },     # student3@osu.com
    { "sub": "auth0|684299388d0f406b0f06d526", "role": "student" },    # student4@osu.com
    { "sub": "auth0|6842994896a28901c3b1f73f", "role": "student" },     # student5@osu.com
    { "sub": "auth0|684299588d0f406b0f06d529", "role": "student" },    # student6@osu.com
]

print("Seeding users...")
for user in users_to_create:
    key = datastore_client.key(USERS_KIND)
    entity = datastore.Entity(key=key)
    entity.update({
        "sub": user["sub"],
        "role": user["role"]
    })
    datastore_client.put(entity)
    print(f"✓ Created {user['role']} with sub={user['sub']} → Datastore ID: {entity.key.id}")
