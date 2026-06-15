from runtime.phase_8_threads.chat import post_user_message

queries = [
    "What is the expense ratio of the HDFC Flexi Cap Fund?",
    "Should I invest in the HDFC Small Cap Fund right now?",
    "Can you check the portfolio balance for my PAN ABCDE1234F?"
]

print("Verifying Pipeline...\n")
for q in queries:
    print(f"Q: {q}")
    try:
        response = post_user_message("test_thread", q)
        print(f"A: {response}\n")
    except Exception as e:
        print(f"Error: {e}\n")
