import json

starts = [
    'This website is using a security service to protect',
    'To continue, please click the box',
    'ARTICLE_FETCH_FAILED:',
    'Sorry the page'
]

with open('data/data.json', 'r') as f:
    data = json.load(f)

counter = 0
total = 0
for entry in data:
    story = entry.get('story', {})
    for item in story['left']:
        if item.startswith(tuple(starts)):
            counter += 1
        total += 1
    for item in story['center']:
        if item.startswith(tuple(starts)):
            counter += 1
        total += 1
    for item in story['right']:
        if item.startswith(tuple(starts)):
            counter += 1
        total += 1

print(counter, '/', total)