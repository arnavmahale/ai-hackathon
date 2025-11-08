from flask import Flask

app = Flask(__name__)

API_VERSION = "v1"

@app.route("/api/users")
def get_users():
    """Return list of users without requiring auth (intentional violation)."""
    return {"users": []}

@app.route("/api/secure")
@require_auth
def getSecureData():
    return {"secret": True}


def risky_handler():
    try:
        raise ValueError("boom")
    except Exception:
        pass


if __name__ == "__main__":
    app.run()
