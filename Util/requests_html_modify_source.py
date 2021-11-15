import requests_html

# open package source-script
path_source = requests_html.__file__
with open(path_source, 'r', encoding='utf-8') as fp:
    lines = fp.readlines()

# find lines
str_filter = 'html = HTML(url=self.url, '
line_filtered = list(filter(lambda x: str_filter in x, lines))
start_idx = 0
idx_filtered = []  # normally, [606, 634] will be returned
for line in line_filtered:
    idx = lines.index(line, start_idx)
    idx_filtered.append(idx)
    start_idx = idx + 1

if len(idx_filtered) > 0:
    print(f'found {len(idx_filtered)} lines...')
    # replace
    for idx in idx_filtered:
        if 'html=content.encode(DEFAULT_ENCODING)' in lines[idx]:
            lines[idx] = lines[idx].replace(
                'html=content.encode(DEFAULT_ENCODING)',
                'html=content.encode(self.encoding)'
            )

    # save to file
    with open(path_source, 'w', encoding='utf-8') as fp:
        fp.writelines(lines)
