def fetch_user_data(user_id):
    # Hardcoded API key
    api_key = "sk-live-1234567890abcdef1234567890abcdef"
    url = f"https://api.example.com/users/{user_id}?token={api_key}"
    return url

def calculate_average(values):
    # Potential division by zero
    total = sum(values)
    return total / len(values)

def process_data(data):
    # Missing docstring and unit test
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
