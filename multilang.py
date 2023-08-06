import pymorphy3
morph = pymorphy3.MorphAnalyzer()


class LangError(Exception):
	pass


def normalize(word, lang):
	if lang == "ru":
		return word.lower().replace("ё", "е")
	else:
		raise LangError("unsupported language")


def lemmatize(word, lang):
	if lang in ("ru", "uk"):
		res = morph.parse(word)
		if res:
			return res[0].normal_form
	else:
		raise LangError("unsupported language")
