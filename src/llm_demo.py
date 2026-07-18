import anthropic

client = anthropic.Anthropic()

msg = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=300,
    messages=[{"role": "user", "content": "In one sentence: what is a city council packet?"}],
)

print(msg.content[0].text)
print("----------------------")
print(msg.usage)

