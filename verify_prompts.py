from news_topic_generator import get_fresh_topic
p = get_fresh_topic()
print("TITLE:", p["title"])
print("FLAGS:", p.get("flags"))
print("NARRATION:", p["narration"][:160])
for s in p["shots"]:
    print(f"  {s['name']}: {s['prompt']}")
