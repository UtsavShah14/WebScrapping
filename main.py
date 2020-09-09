import flask as f
import joblib
import pandas as pd
import tweepy as tw

import Access_Keys
from country import country_bounding_boxes
import preprocessing_data

consumer_API_key = Access_Keys.consumer_API_key
consumer_API_secret_key = Access_Keys.consumer_API_secret_key
access_token = Access_Keys.access_token
access_token_secret = Access_Keys.access_token_secret

app = f.Flask(__name__)
app.secret_key = 'hello'


@app.route('/')
def index():
    if 'username' in f.session:
        template_values = {
            'country_list': country_bounding_boxes,
            'test': None,
            'username': f.session['username'],
            'query_tweet': None,
            'prediction': False,
            'logr_prediction': None,
            'svm_prediction': None
        }
        return f.render_template('index.html', **template_values)
    return "You are not logged in, please login in to continue.<br><a href = '/login'>" + "click here to login</a>"


@app.route('/login', methods=['POST', 'GET'])
def login():
    if f.request.method == 'POST':
        f.session['username'] = f.request.form['username']
        return f.redirect(f.url_for('index'))
    else:
        return f.render_template('login.html')


@app.route('/logout')
def logout():
    f.session.pop('username', None)
    return f.redirect(f.url_for('index'))


@app.route('/output', methods=['POST'])
def tweet_search():
    if f.request.method == 'POST':
        search_word, date_since, location = ts.request_input()
        tweets = ts.get_tweet(search_word, date_since, location, api)
        query_tweet, query_location = ts.tweet_to_list(tweets)

        if not query_tweet:
            f.flash("Could not retrieve any tweets")
            return f.redirect(f.url_for('index'))

        svm_prediction, logr_prediction = ts.predict_values(query_tweet)

        total_tweets = len(query_tweet)

        percentage_positive, percentage_negative, percentage_neutral = ts.get_percentage(
            svm_prediction, logr_prediction, total_tweets)

        graph_data = ts.plot_graph(percentage_positive, percentage_negative, percentage_neutral)
        template_values = {
            'country_list': country_bounding_boxes,
            'test': graph_data,
            'username': f.session['username'],
            'query_tweet': query_tweet,
            'prediction': True,
            'logr_prediction': logr_prediction,
            'svm_prediction': svm_prediction
        }
        return f.render_template('index.html', **template_values)
    else:
        return f.render_template('login.html')


class TwitterStreamer:

    @staticmethod
    def authenticate():
        auth = tw.OAuthHandler(consumer_API_key, consumer_API_secret_key)
        auth.set_access_token(access_token, access_token_secret)
        api = tw.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
        return api

    @staticmethod
    def get_tweet(search_words, date_since, location, api_call):
        max_tweets = 500
        tweets = tw.Cursor(
            api_call.search,
            q=search_words,
            geocode=location,
            lang="en",
            since=date_since,
            tweet_mode='extended'
        ).items(max_tweets)
        return tweets

    @staticmethod
    def display_tweets(tweets):
        pd.set_option('display.max_columns', None)
        data = [[tweet.text, tweet.user.screen_name, tweet.user.location] for tweet in tweets]
        tweet_text = pd.DataFrame(data=data, columns=['tweets', 'user', "location"])
        print(tweet_text)
        return tweet_text

    @staticmethod
    def request_input():
        search_word = f.request.form['search word'] + '-filter:retweets'
        date_since = f.request.form['date']
        geocode = f.request.form['location']
        if geocode != 'world':
            geocode = list(country_bounding_boxes[geocode][1])
            geocode.pop()
            geocode.pop()
            geocode.append('3000km')
            location = ','.join([str(elem) for elem in geocode])
        else:
            location = None
        return search_word, date_since, location

    @staticmethod
    def tweet_to_list(tweets):
        query_tweet = []
        query_location = []
        for tweet in tweets:
            query_tweet.append(preprocessing_data.get_clean_text(tweet.full_text))
            query_location.append(tweet.user.location)
        return query_tweet, query_location

    @staticmethod
    def predict_values(query_tweet):
        vectorizer = joblib.load('vectorizer.sav')
        X = vectorizer.transform(query_tweet)
        svm = joblib.load('svm_classifier.sav')
        logr = joblib.load('logr_classifier.sav')
        svm_prediction = svm.predict(X)
        logr_prediction = logr.predict(X)
        return svm_prediction, logr_prediction

    @staticmethod
    def get_percentage(svm_prediction, logr_prediction, total_tweets):
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        for pred in logr_prediction:
            if pred == 'positive':
                positive_count += 1
            elif pred == 'negative':
                negative_count += 1
            else:
                neutral_count += 1
        percentage_positive = (positive_count / total_tweets) * 100
        percentage_negative = (negative_count / total_tweets) * 100
        percentage_neutral = (neutral_count / total_tweets) * 100
        return percentage_positive, percentage_negative, percentage_neutral

    @staticmethod
    def plot_graph(percentage_positive, percentage_negative, percentage_neutral):
        categories = ['positive', 'negative', 'neutral']
        values = [percentage_positive, percentage_negative, percentage_neutral]
        # color = {'positive': 'Green', 'negative': 'Red', 'neutral': 'Yellow'}
        color = ['#158467', '#e84a5f', '#fddb3a']
        data = [{
            'values': values,
            'labels': categories,
            'hole': '0.4',
            'type': 'pie',
            'marker': {
                'colors': color
            },
            'textinfo': 'label+percent',
            'hoverinfo': 'label+percent',
        }]
        return data


if __name__ == '__main__':
    ts = TwitterStreamer()
    api = ts.authenticate()
    app.run(debug=True)
