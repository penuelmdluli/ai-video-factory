"""Verify that profile pics and cover photos are set on all pages."""
import sys
import requests

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

PAGES = [
    {
        "key": "ai_trading",
        "name": "Beast Mode Academy",
        "page_id": "103551448238854",
        "token": "EAAIaAVdodLYBQwYBr3s9H7bEXhZAMb4XAy1TTbdZCjYdbMBj1Tb8d7tw1hvIkClqzU8s395dFYjhhG8tPdwMc9GnZApZAkS2nG6LaOiBcaFvo0IZCZAnAMZCSaTAMn2IPAoou4VwvRPZCX74fIRqtsfH1RJ4ZCH43JPO8sqiRo3H3Y6e4ONngDv77j4pKZA5BTsZBouGhcHp9VxqSyQcdh1j6UBD4OUXZAXvxGGGkgwWWtpDVJZCH2NjsEsl5RzOoEwZDZD",
    },
    {
        "key": "ai_money",
        "name": "Smart Money AI",
        "page_id": "100919755007786",
        "token": "EAAIaAVdodLYBQZBDd10klIlrbmuT1fu4QqGbb5jKfyntpUXDUTGXwSIUdnK9lqyQkmV0ZCT2r3y4DEAlDGQezvE7C0X83txikISnHzAI6ZCsrf6DQb8QsZArSxiqpwA0H5gSSZBMDp6gsx1ZArqxNguUHEjrhPzZC9C41JJslgzniNHMAIWRLUbKACQLMrmz4hCZBZAJSNXZADPUFX1FkHM4Pg5nFtWvhBCeOLiZBQPCv9GCdGPiaAgWZCmTAYpOMwZDZD",
    },
    {
        "key": "tech_news",
        "name": "Tech Pulse Africa",
        "page_id": "107465491085378",
        "token": "EAAIaAVdodLYBQwv0WpNIYfKs01HB4PorZCP4dgM7bvZBF9KuNZAajozLZBbNKrUZCCuMOwGcmIxA7IOBlOZCEd7tfG1XjgbFHal6vXvfw1TeW004nSC2P4nNI1ZBU23f3w2GlzP23YnEkQSt7kHYZC6MHbps3tqmv7idn2dQ6IBI6aQr734ZAJdtEX272I2snu24f9AeAAhrmZCU2sEOAGXbsBynZAwF8WCuZAaxGZBtKSPqWBctH0bD0gxibHU5IDAZDZD",
    },
    {
        "key": "motivation",
        "name": "Elevate You",
        "page_id": "102206758210905",
        "token": "EAAIaAVdodLYBQ2rK1JxgBS9PZCVzinlLQzP3OO1qp0KX61rJxCa9m5ouWhv7hvT0WeZAefY6vOfGOT6wfa1UhvAbby4GyottwxdejGAFZBiS2ndjjGjHYvyj7p2GnNqbOOpk9ExpZCHeX9af31ppTDkB2vdbYmO1HIwWzMY7MrsmskMtC0qWMwXuIPQcLQt48fja0gZAX31gFfg2GsZC67jESmioIqxTaor6ZBeCe1FLzZBP4hA0pyI1B5OciAZDZD",
    },
    {
        "key": "health_wellness",
        "name": "Herbal Organic Life",
        "page_id": "106788301081578",
        "token": "EAAIaAVdodLYBQyVjnpoA5UwHvOjWK7x6Ks9b1NSA2L3Cy0mLOzQw2FZAVZAshfT6TYekkRPN6QWKgmCg5habWvUaQKoxNlPmmA7fqh8EsbKHUwZBGbcbG9KZAng6s4uFEKZBc0nmqZC9GoI7B4gY9pD3XZACBQXHi0XYoJH1DQfwWPxXpiExYZAWjz2W6sEMtGKoVNr70soeYfDS51wn2jxsZC7bqm3s5oZAXmsqoTj09fOyDpa8BxWE27TYzk4QZDZD",
    },
]


def main():
    for page in PAGES:
        print(f"\n{'='*60}")
        print(f"{page['name']} (ID: {page['page_id']})")
        print(f"{'='*60}")

        # Check page info including cover
        resp = requests.get(
            f"https://graph.facebook.com/v24.0/{page['page_id']}",
            params={
                "access_token": page["token"],
                "fields": "id,name,cover,picture",
            },
            timeout=30,
        )
        data = resp.json()

        if "error" in data:
            print(f"  ERROR: {data['error']['message']}")
            continue

        print(f"  Name: {data.get('name', 'N/A')}")

        # Cover photo
        cover = data.get("cover")
        if cover:
            print(f"  Cover photo: SET")
            print(f"    Cover ID: {cover.get('id', 'N/A')}")
            print(f"    Cover URL: {cover.get('source', 'N/A')[:100]}...")
        else:
            print(f"  Cover photo: NOT SET")

        # Profile picture
        picture = data.get("picture")
        if picture:
            pic_data = picture.get("data", {})
            print(f"  Profile pic: SET")
            print(f"    URL: {pic_data.get('url', 'N/A')[:100]}...")
            print(f"    Is silhouette: {pic_data.get('is_silhouette', 'N/A')}")
        else:
            print(f"  Profile pic: NOT SET")


if __name__ == "__main__":
    main()
