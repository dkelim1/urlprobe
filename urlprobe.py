from datetime import datetime, timedelta
import requests, sys, time
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, update
from flask_apscheduler import APScheduler

url_list = []
url_data = []

summary_interval = 50  # in secs
delete_duration = 30   # in mins
delete_interval = 10   # in secs
probe_interval = 5     # in secs
csv_size = 5
counter = 0

app = Flask(__name__)
scheduler = APScheduler()

##CREATE DATABASE
db_file = "probe_url_stats.db"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + db_file

# Create the extension
url_probe_db = SQLAlchemy()
# Initialise the app with the extension
url_probe_db.init_app(app)

##CREATE TABLE
class urlProbeStats(url_probe_db.Model):
    insert_time = url_probe_db.Column(url_probe_db.String(250), primary_key=True)
    name = url_probe_db.Column(url_probe_db.String(250), nullable=False)
    url = url_probe_db.Column(url_probe_db.String(250), nullable=False)
    http200 = url_probe_db.Column(url_probe_db.Integer, nullable=False)
    http300 = url_probe_db.Column(url_probe_db.Integer, nullable=False)
    http400 = url_probe_db.Column(url_probe_db.Integer, nullable=False)
    http500 = url_probe_db.Column(url_probe_db.Integer, nullable=False)

class urlProbeSummary(url_probe_db.Model):
    name = url_probe_db.Column(url_probe_db.String(250), nullable=False, primary_key=True)
    url = url_probe_db.Column(url_probe_db.String(250), nullable=False)
    past_datetime = url_probe_db.Column(url_probe_db.String(250), nullable=False)
    http200_sum = url_probe_db.Column(url_probe_db.Integer, nullable=False)
    http300_sum = url_probe_db.Column(url_probe_db.Integer, nullable=False)
    http400_sum = url_probe_db.Column(url_probe_db.Integer, nullable=False)
    http500_sum = url_probe_db.Column(url_probe_db.Integer, nullable=False)

# Create table schema in the database. Requires application context.
with app.app_context():
    url_probe_db.create_all()

def getURLs():

    with open("url_list.csv", "r") as url_file:
        csv_len = len(url_file.readlines())
    url_file.close()

    if csv_len > int(csv_size+1):
        print(f"Number of rows is larger than {csv_size}!! Exiting script...")
        sys.exit()
    
    #for all records
    with app.app_context():
        url_probe_db.session.query(urlProbeSummary).delete()
        url_probe_db.session.commit()

    with open("url_list.csv", "r") as url_file:

        headers = next(url_file).strip().replace(" ","").split(",")

        for row in url_file:
            url_list = row.strip().replace(" ","").split(",")
            url_data.append(dict(zip(headers, url_list)))
            url_dict = dict(zip(headers, url_list), past_datetime = "(PAST DATE & TIME)", http200_sum = 0, http300_sum = 0, http400_sum = 0, http500_sum = 0)
            with app.app_context():
                new_record = urlProbeSummary(name=url_dict["name"], url=url_dict["url"], past_datetime=url_dict["past_datetime"], http200_sum=url_dict["http200_sum"], http300_sum=url_dict["http300_sum"], http400_sum=url_dict["http400_sum"], http500_sum=url_dict["http500_sum"])
                url_probe_db.session.add(new_record)
                url_probe_db.session.commit()

    url_file.close()


@app.route('/')
def prtProbeSummary():
    url_summary = urlProbeSummary.query.all()
    # print(f"summary_interval_min {summary_interval / 60, 3}")
    return render_template('default.jinja2', url_summary=url_summary, summary_interval_min=round(summary_interval / 60, 3), summary_interval_sec = summary_interval, probe_interval=probe_interval)


def probeStatsDelete():
     
     housekeep_date_time = datetime.now() - timedelta(minutes=delete_duration)
     print(f"Based on Deletion DT - {housekeep_date_time}")

     with app.app_context():
        url_probe_db.session.execute(url_probe_db.delete(urlProbeStats).where(urlProbeStats.insert_time < housekeep_date_time))
        url_probe_db.session.commit()


def probeSummary():

    with app.app_context():
        stmt = (update(urlProbeSummary).values(http200_sum = 0,http300_sum = 0,http400_sum = 0,http500_sum = 0))
        url_probe_db.session.execute(stmt)
        url_probe_db.session.commit()

    past_date_time = datetime.now() - timedelta(seconds=summary_interval + 1)

    # Display summary of probe status for the past number of seconds defined by variable summary_interval 
    print(f"Displaying items since the past {summary_interval} secs")
    print(f"Past date_time : {past_date_time}")

    with app.app_context():
        probe_results = url_probe_db.session.execute(url_probe_db.select(urlProbeStats.insert_time,urlProbeStats.name,urlProbeStats.url,urlProbeStats.http200,urlProbeStats.http300,urlProbeStats.http400,urlProbeStats.http500).where(urlProbeStats.insert_time > past_date_time).order_by(desc(urlProbeStats.insert_time))).all()       
        print(f"ProbeStats - {probe_results}")
        
    for url_item in probe_results:
        print(f"Name        = {url_item[1]}")
        print(f"URL         = {url_item[2]}")
        print(f"HTTP 200    = {url_item[3]}")
        print(f"HTTP 300    = {url_item[4]}")
        print(f"HTTP 400    = {url_item[5]}")
        print(f"HTTP 500    = {url_item[6]}")

        with app.app_context():
            probe_summary = url_probe_db.session.execute(url_probe_db.select(urlProbeSummary).where(urlProbeSummary.name==url_item[1])).scalar()
            probe_summary.http200_sum = probe_summary.http200_sum + url_item[3]
            probe_summary.http300_sum = probe_summary.http300_sum + url_item[4]
            probe_summary.http400_sum = probe_summary.http400_sum + url_item[5]
            probe_summary.http500_sum = probe_summary.http500_sum + url_item[6]
            probe_summary.past_datetime = past_date_time.strftime("%Y-%m-%d %H:%M:%S")
            url_probe_db.session.commit()


def probeURLs():
        
    global counter

    while 1:

        while 1:
            counter = counter + 1
            print(f"HTTP Probe No :- {counter}")

            for url_entry in url_data:
            
                try:
                    with requests.get(url_entry["url"], timeout=5) as response:

                        if  response.status_code >= 200 and response.status_code <= 299:
                            with app.app_context():
                                new_record = urlProbeStats(insert_time=datetime.now(), name=url_entry["name"], url=url_entry["url"], http200=1, http300=0, http400=0, http500=0)
                                url_probe_db.session.add(new_record)
                                url_probe_db.session.commit()
                        elif response.status_code >= 300 and response.status_code <= 399:
                            with app.app_context():
                                new_record = urlProbeStats(insert_time=datetime.now(), name=url_entry["name"], url=url_entry["url"], http200=0, http300=1, http400=0, http500=0)
                                url_probe_db.session.add(new_record)
                                url_probe_db.session.commit()
                        elif response.status_code>= 400 and response.status_code <= 499:
                            with app.app_context():
                                new_record = urlProbeStats(insert_time=datetime.now(), name=url_entry["name"], url=url_entry["url"], http200=0, http300=0, http400=1, http500=0)
                                url_probe_db.session.add(new_record)
                                url_probe_db.session.commit()
                        elif response.status_code >= 500 and response.status_code <= 599:
                            with app.app_context():
                                new_record = urlProbeStats(insert_time=datetime.now(), name=url_entry["name"], url=url_entry["url"], http200=0, http300=0, http400=0, http500=1)
                                url_probe_db.session.add(new_record)
                                url_probe_db.session.commit()

                    response.raise_for_status()

                except requests.ConnectTimeout:
                    continue
                except requests.ReadTimeout:
                    continue
                except requests.ConnectionError:
                    continue
                except requests.HTTPError:
                    continue
                except requests.URLRequired:
                    continue
                except requests.TooManyRedirects:
                    continue
                except requests.Timeout:
                    continue

            time.sleep(probe_interval)
        
getURLs()

if __name__ == '__main__':
    scheduler.add_job(id = 'Probe URLs', func=probeURLs)
    scheduler.add_job(id = 'Probe URLs Summary', func=probeSummary, trigger="interval", seconds=summary_interval)
    scheduler.add_job(id = 'Delete URLs Statistics', func=probeStatsDelete, trigger="interval", seconds=delete_interval)
    scheduler.start()
    app.run(host="0.0.0.0",port=8000,debug=False,)
    
    
