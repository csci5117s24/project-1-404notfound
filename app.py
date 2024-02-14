import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for
import db_helper as db

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__)
app.secret_key = env.get("APP_SECRET_KEY")



oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration',
)


@app.route("/")
def home():
    return render_template(
        "home.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
    )

@app.route('/art/<id>')
def art(id):
    return render_template('art_page.html', art_id=id)

@app.route("/user_profile")
def user_profile():
    # Check if user data is in the session
    user_info = session.get('user')
    
    if not user_info:
        # Redirect to login page or handle the case where there is no user info
        return redirect(url_for('login'))

    # Assuming the user_info contains all the necessary data
    user_data = {
        'name': user_info.get('name'),  
        'email': user_info.get('email'),  
        'description': 'Description start here',  # Store this in the session or database as well
        'subscriptions': 0,  
        'fans': 0,  
        'likes': 0,  # This should come from the database or session
        'artworks': ['Template 1', 'Template 2', 'Template 3', 'Template 4']  # This list should come from the session
    }
    return render_template('user_profile.html', user=user_data)

@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    print(token,flush=True)
    session["user"] = token

    user_info = token['userinfo']
    store_new_user(user_info)
    return redirect("/")

def store_new_user(user_info):
    user = db.query_db(
        "SELECT * FROM users WHERE auth0_user_id = %s", (user_info["sub"],), one=True
    )
    if user is None:
        db.modify_db(
            "INSERT INTO users (auth0_user_id, email) VALUES (%s, %s)",
            (user_info["sub"], user_info["email"]),
        )
    return





@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://"
        + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


if __name__ == "__main__":
    with app.app_context():
        db.init_db_pool()
    app.run(debug=True)
    # app.run(host="0.0.0.0", port=env.get("PORT", 3000))
