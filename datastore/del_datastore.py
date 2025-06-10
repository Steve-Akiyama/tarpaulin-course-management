from google.cloud import datastore

# Make sure your GOOGLE_CLOUD_PROJECT env var is set (or that your Application Default Credentials are pointing at the right project).
client = datastore.Client()

# List all your kinds here. Add any other kinds you’ve created.
kinds_to_clear = ["users", "courses"]  

for kind in kinds_to_clear:
    # Query for all keys in this kind
    query = client.query(kind=kind)
    query.keys_only()  # we only need the keys
    keys = [entity.key for entity in query.fetch()]
    if not keys:
        print(f"No entities to delete in kind: {kind}")
        continue

    # Delete in batches of 500 (max allowed by delete_multi)
    BATCH_SIZE = 500
    for i in range(0, len(keys), BATCH_SIZE):
        batch = keys[i : i + BATCH_SIZE]
        client.delete_multi(batch)
        print(f"Deleted {len(batch)} entities from kind '{kind}'")

print("🚮 Datastore wipe complete.")
