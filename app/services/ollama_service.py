import requests

def ask_ollama(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        data = response.json()
        return data.get("response", "No response from Ollama")

    except Exception as e:
        return f"Ollama Error: {str(e)}"