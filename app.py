import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for, request
import db_helper as db
import boto3

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
s3_client = boto3.client(
    "s3",
    aws_access_key_id=env.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=env.get("AWS_SECRET_ACCESS_KEY"),
    region_name=env.get("S3_REGION")
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
    return render_template('art_page.html', session=session.get("user"), art_id=id)

@app.route("/user_profile")
def user_profile():
    # Check if user data is in the session
    user_info = session.get('user')
    
    if not user_info:
        # Redirect to login page or handle the case where there is no user info
        return redirect(url_for('login'))

    # Assuming the user_info contains all the necessary data
    user_id = user_info['userinfo']['user_id']
    print("user_id:",user_id, flush=True)
    
    user_data = {
        'name': user_info['userinfo']['name'],  
        'email': user_info['userinfo']['email'],  
        'description': 'Description start here',  # Store this in the session or database as well
        'subscriptions': get_user_subscriptions(user_id),  
        'fans': get_user_fans(user_id),  
        'likes': get_user_likes(user_id),  # This should come from the database or session
    #     'artworks': [
    #     {'title': 'Artwork 1', 'url': 'images/sample.png'},
    #     {'title': 'Artwork 2', 'url': 'images/art.png'},
    #     {'title': 'Artwork 3', 'url': 'images/sample.png'},
    # ]
        'artworks': get_user_artworks(user_id)
    }
    return render_template('user_profile.html', user=user_data)
def get_user_likes(user_id):
    likes = db.query_db(
        "SELECT COUNT(*) FROM image_interactions WHERE user_id = %s AND liked = TRUE", (user_id,),one=True
    )
    return likes[0] if likes else 0
def get_user_fans(user_id):
    fans = db.query_db(
        "SELECT COUNT(*) FROM follows WHERE following_id = %s", (user_id,),one=True
    )
    return fans[0] if fans else 0
def get_user_subscriptions(user_id):
    subscriptions = db.query_db(
        "SELECT COUNT(*) FROM follows WHERE follower_id = %s", (user_id,),one=True
    )
    return subscriptions[0] if subscriptions else 0
def get_user_artworks(user_id):
    artworks = db.query_db(
        "SELECT * FROM images WHERE user_id = %s", (user_id,)
    )
    print("artworks:",artworks, flush=True)
    return artworks

def get_trending_artworks():
    # get the top 10 artworks based on the number of likes and time of upload
    artworks = db.query_db(
        "SELECT * FROM images ORDER BY created_at DESC LIMIT 10"
    )
    
@app.route('/update_description', methods=['POST'])
def update_description():
    # Make sure the user is logged in
    if 'user' in session and session['user']:
        new_description = request.form.get('description')
        # Update
        session['user']['description'] = new_description
        
        # Redirect back to the profile page
        return redirect(url_for('user_profile'))
    else:
        return redirect(url_for('login'))


def some_route_function():
    image_path_art = url_for('static', filename='images/art.png')
    image_path_sample = url_for('static', filename='images/sample.png')
    # Now you can pass these paths to your template
    return render_template('your_template.html', art_image=image_path_art, sample_image=image_path_sample)

@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token

    user_info = token['userinfo']
    store_new_user(user_info)
    return redirect("/")

def store_new_user(user_info):
    userID = db.query_db(
        "SELECT user_id FROM users WHERE auth0_user_id = %s", (user_info["sub"],), one=True
    )
    if userID is None:
        db.modify_db(
            "INSERT INTO users (auth0_user_id, email) VALUES (%s, %s)",
            (user_info["sub"], user_info["email"]),
        )
        userID = db.query_db(
            "SELECT user_id FROM users WHERE auth0_user_id = %s", (user_info["sub"],), one=True
        )

    #get user id from db and store in session
    # print("userID:",userID[0], flush=True)
    
    session['user']['userinfo']['user_id'] = userID[0]
        
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

@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        if 'image' not in request.files:
            return "No file part", 400
        image = request.files['image']
        if image.filename == '':
            return "No selected file",  400
        if image:
            image_url = upload_image_to_s3(image)
            title = request.form.get("title", "")
            description = request.form.get("description", "")
            prompt = request.form.get("prompt", "")
            user_id = session["user"]["user_id"] 
            # user_id = 1
            db.modify_db(
                "INSERT INTO images (user_id, title, description, image_url, prompt) VALUES (%s, %s, %s, %s, %s)",
                (user_id, title, description, image_url, prompt),
            )
            return 'Image uploaded successfully!', 200
    return render_template("upload.html")


def upload_image_to_s3(image):
    s3_client.upload_fileobj(
        image,
        env.get("S3_BUCKET"),
        image.filename,
        ExtraArgs={"ContentType": image.content_type},
    )
    return f"https://{env.get('S3_BUCKET')}.s3.amazonaws.com/{image.filename}"



if __name__ == "__main__":
    with app.app_context():
        db.init_db_pool()
    app.run(debug=True)
    # app.run(host="0.0.0.0", port=env.get("PORT", 3000))
