import os
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

# Initialize the OpenAI client with the API key
client = openai.OpenAI(api_key=api_key)

# Define the prompt for the poem
prompt = "Write a short, beautiful poem about AI tinkerers and the best meetup for AI engineers in the world."

# Generate the poem using the OpenAI API
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a creative poet who writes beautiful, concise poems."},
        {"role": "user", "content": prompt}
    ],
    max_tokens=300
)

# Extract the poem from the response
poem = response.choices[0].message.content

# Print the poem
print("\n--- AI-Generated Poem ---\n")
print(poem)
print("\n-------------------------\n") 