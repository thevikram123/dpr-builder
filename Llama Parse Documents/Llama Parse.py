from llama_cloud import AsyncLlamaCloud

client = AsyncLlamaCloud(api_key="llx-...")

# Upload and parse a document
file_obj = await client.files.create(file="./attention_is_all_you_need.pdf", purpose="parse")

result = await client.parsing.parse(
    file_id=file_obj.id,
    # The parsing tier. Options: fast, cost_effective, agentic, agentic_plus,
    tier="cost_effective",
    # The version of the parsing tier to use. Use 'latest' for the most recent version,
    version="latest",
    # 'expand' controls which result fields are returned in the response.,
    # Without it, only job metadata is returned. Common fields:,
    # - "markdown_full", "text_full": Full document content,
    # - "markdown", "text", "items": Page-level content,
    # - "images_content_metadata": Presigned URLs for images,
    expand=["markdown_full", "text_full"],
)

# Access the full document content
print("Full markdown:")
print(result.markdown_full)

print("\nFull text:")
print(result.text_full)
