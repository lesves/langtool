import pymorphy3
morph = pymorphy3.MorphAnalyzer()


class LangError(Exception):
	pass


def normalize(word, lang):
	if lang == "ru":
		return word.lower().replace("ё", "е")
	else:
		raise LangError("unsupported language")


def lemmatize(word, lang, normalize=True, normalize_fn=normalize):
	if lang in ("ru", "uk"):
		res = morph.parse(word)
		if res:
			if normalize:
				return normalize_fn(res[0].normal_form, lang)
			else:
				return res[0].normal_form
	else:
		raise LangError("unsupported language")
