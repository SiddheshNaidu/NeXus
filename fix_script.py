import os

def fix_file(path, replacements):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in replacements:
        content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

fix_file('frontend/src/components/ui/aether-flow-hero.tsx', [
    ('                             ctx.strokeStyle = \ngba(255, 255, 255, );', '                             ctx.strokeStyle = `rgba(255, 255, 255, ${opacityValue})`;'),
    ('                             ctx.strokeStyle = \ngba(99, 102, 241, );', '                             ctx.strokeStyle = `rgba(99, 102, 241, ${opacityValue})`;')
])

fix_file('frontend/src/components/ui/story-section.tsx', [
    ('backgroundImage: url("data:', 'backgroundImage: `url("data:'),
    ('%3C/svg%3E")\n', '%3C/svg%3E")`\n')
])

print('Files fixed')
