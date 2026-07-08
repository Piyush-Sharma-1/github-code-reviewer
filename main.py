from config import GROQ_API_KEY, GITHUB_TOKEN

def main():
    print("Config loaded successfully.")
    print("Groq key present:", GROQ_API_KEY is not None)
    print("GitHub token present:", GITHUB_TOKEN is not None)

if __name__ == "__main__":
    main()