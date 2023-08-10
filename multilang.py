import simplemma

import pymorphy3
morph = pymorphy3.MorphAnalyzer()


supported = ("cs", "en", "ru")


class LangError(Exception):
	pass


def normalize(word, lang):
	if lang == "cs":
		return word.lower()
	elif lang == "en":
		return word.lower()
	elif lang == "ru":
		return word.lower().replace("ё", "е")
	else:
		raise LangError("unsupported language")


def lemmatize(word, lang, normalize=True, normalize_fn=normalize):
	if lang not in supported:
		raise LangError("unsupported language")

	norm = lambda x: normalize_fn(x, lang) if normalize else x

	if lang in ("ru", "uk"):
		res = morph.parse(word)
		if res:
			return norm(res[0].normal_form)
	else:
		return norm(simplemma.lemmatize(word, lang=lang))
