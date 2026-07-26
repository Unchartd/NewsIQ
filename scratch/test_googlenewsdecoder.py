import asyncio
from googlenewsdecoder import new_decoderv1

async def main():
    url = "https://news.google.com/rss/articles/CBMi7AFBVV95cUxQbDlmQi1hVjdnMlg2UjEzWXRUVEVRdDc3UGZBUGh5eHVMSURHWEMwUnNvZ2pMaHBkSjF5U0MxdGUxaWN3d2hkSkdvbm00RmJreVlFb2Y0UE1CdjgySkE0bU1ZWHQyS0NTLTdnQlFHeTgtc25Gdm03RW95RnFDQnFGQnZVWllrUU5rUUZndnZxZmI4ZXpSbERNUnUzYXdUeUNwaXQ5c0hRSkM4VmZyeDF6dHh6Skx1NGVIYnFhNlBrQTlvZ3FLdjhpWGZvUTUwcE5VbjVEOEFKazlpWWtkelI3MVhyRFVFaVZxcWhkONIB8gFBVV95cUxNU2JJbE1SSmVuWVh1RFdBc29ueTNNNEFvaVM1QjhYWFI1cUVYYUpaUXhCUnpiNkpvY2FtSlNKTEpiRDVLRnFpT3VXUVpjQXJNeTJRRHVBWUQteF9XcHZXTDU5VlJ6VmNyT0daOC1nSlFJbHB2THNUWjVwNHo4R3I4X1BmeExwSW42MmQzd2VGa0hzZWlXSkdNZ2EtclRJVVhhX21YM1pDdWhhZjJmQjdTS0Jpb3paa3A2emNLR09iQ2EtT2xpVDVqaE1FUzdiY1JpbzVrazd2SG9LR04yUzJUTUplNmo1NFJNZVkyTmlNUjZMZw?oc=5"
    print("Testing googlenewsdecoder.new_decoderv1...")
    try:
        decoded = new_decoderv1(url, interval=1)
        print("Response object type:", type(decoded))
        print("Response contents:", decoded)
    except Exception as e:
        print("Failed to decode:", e)

if __name__ == "__main__":
    asyncio.run(main())
