import logging

from app.workers.tasks import cluster_news_task

logging.basicConfig(level=logging.INFO)

def main():
    print("Triggering news clustering task...")
    cluster_news_task()
    print("News clustering task finished.")

if __name__ == "__main__":
    main()
