import re
DOC = '''docstring mentions C:\temp but is not a path use'''
RX = re.compile("a\\d+\\b+")
def uses(open):
    return open(r"C:\temp\x.txt")
