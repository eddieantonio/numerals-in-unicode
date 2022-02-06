CURL = curl --silent --fail --show-error

.PHONY: download test
download: UnicodeData.txt Scripts.txt

test:
	python3 -m doctest codepoint.py
	python3 -m doctest parse_ucd.py


UnicodeData.txt:
	$(CURL) -o $@ 'https://www.unicode.org/Public/14.0.0/ucd/UnicodeData.txt'
Scripts.txt:
	$(CURL) -o $@ 'https://www.unicode.org/Public/14.0.0/ucd/Scripts.txt'
