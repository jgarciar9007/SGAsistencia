import io
text = io.open('remote_tb.txt', encoding='utf-16le').read()
lines = text.split('\n')
with open('tb_out.txt', 'w', encoding='utf-8') as out:
    for line in lines[-150:]:
        out.write(line + '\n')
