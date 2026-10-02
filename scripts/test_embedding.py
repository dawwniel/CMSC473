from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

prompts = [
    "fast blue magical sparks",
    "slow floating smoke",
    "large fiery explosion",
]

embeddings = model.encode(prompts)

print("Shape:", embeddings.shape)

for prompt, embedding in zip(prompts, embeddings):
    print(prompt)
    print(embedding[:10])
    print()