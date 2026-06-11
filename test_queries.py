import requests

url = "http://localhost:8000/api/chat"

queries = [
    "What is the expense ratio of the HDFC Flexi Cap Fund?",
    "Should I invest in the HDFC Small Cap Fund right now?",
    "Can you check the portfolio balance for my PAN ABCDE1234F?"
]

print("Testing API...")
for q in queries:
    print(f"\nQ: {q}")
    response = requests.post(url, json={"thread_id": "test_thread", "message": q})
    if response.status_code == 200:
        print(f"A: {response.json().get('message')}")
    else:
        print(f"Error: {response.text}")
