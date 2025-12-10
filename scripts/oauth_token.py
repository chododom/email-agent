# This script is meant to be run one time for the initial setup of a Gmail inbox watch.
# It takes a client secret from a configured OAuth client in GCP and authenticates a specific
# user, whose credentials are then stored in the output token.
# Save the output token in Secret Manager and use for all further authentication and refreshing.

import os.path
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes needed for reading and sending
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

INPUT_CLIENT_SECRET_FILE = "client_secret2.json"
OUTPUT_TOKEN_FILE = "token2.json"


def main():
    flow = InstalledAppFlow.from_client_secrets_file(INPUT_CLIENT_SECRET_FILE, SCOPES)

    # This will open a browser window for you to log in
    creds = flow.run_local_server(port=0)

    # Save the credentials (including refresh token) to a file
    with open(OUTPUT_TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

    print(f"Success! {OUTPUT_TOKEN_FILE} created. This file contains your secret key.")


if __name__ == "__main__":
    main()
