CURL = curl --silent --fail --show-error

all: UnicodeData.txt Scripts.txt

UnicodeData.txt:
	$(CURL) -o $@ 'https://www.unicode.org/Public/13.0.0/ucd/UnicodeData.txt'
Scripts.txt:
	$(CURL) -o $@ 'https://www.unicode.org/Public/13.0.0/ucd/Scripts.txt'
