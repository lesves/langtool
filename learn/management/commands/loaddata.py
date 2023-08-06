from django.core.management.base import CommandError
from django_tqdm import BaseCommand

from django.db import transaction
from django.db.models import Q

from django.conf import settings

from learn.models import Language, Sentence, Word

from multilang import normalize, lemmatize
from wordfreq import word_frequency

from itertools import islice

import csv
import re


class Command(BaseCommand):
    help = "Load data for selected language pairs (in settings) to the database"

    pairs = settings.LANGTOOL_LANGUAGE_PAIRS
    nwords = settings.LANGTOOL_LANGUAGE_TOP_N_WORDS

    @transaction.atomic
    def handle(self, *args, **options):
        self.setup_languages()
        self.load_sentences()
        self.load_voice()
        self.link_words()

    def setup_languages(self):
        Language.objects.bulk_create([
            Language(code, name, native_name) 
            for code, name, native_name in settings.LANGTOOL_LANGUAGES
        ], ignore_conflicts=True)

    def load_sentences(self):
        for one, two in self.pairs:
            self.stdout.write(f"Loading {one}-{two} sentences.")
            with open(f"data/{two}-{one}-tatoeba.tsv") as f:
                # Skip BOM
                if f.read(1) != "\ufeff":
                    f.seek(0)

                reader = csv.reader(f, delimiter="\t")

                for sent_id, sent_text, trans_id, trans_text in self.tqdm(reader):
                    sent_id = int(sent_id.strip())
                    trans_id = int(trans_id.strip())

                    trans, _ = Sentence.objects.get_or_create(link_id=trans_id, text=trans_text, lang=Language.objects.get(code=one))
                    sent, _ = Sentence.objects.get_or_create(link_id=sent_id, text=sent_text, lang=Language.objects.get(code=two))
                    sent.translations.add(trans)

        self.stdout.write(self.style.SUCCESS("Sentences loaded."))

    def link_words(self):
        for _, code in self.pairs:
            lang = Language.objects.get(code=code)
            self.stdout.write(f"Building words for {lang}.")

            with open(f"data/{code}-freq.tsv") as f:
                reader = csv.reader(f, delimiter="\t")

                for _ in range(self.nwords[code]):
                    (_, _, w) = next(reader)
                    Word.objects.get_or_create(text=w, lang=lang)

            self.stdout.write(f"Linking words in {lang} with sentences.")

            for sent in self.tqdm(Sentence.objects.filter(lang=lang)):
                for w in sent.tokens:
                    try:
                        sent.words.add(Word.objects.get(lang=lang, text=normalize(lemmatize(w, code), code)))
                    except Word.DoesNotExist:
                        pass

        self.stdout.write(self.style.SUCCESS("Words linked."))

    def load_voice(self):
        for _, code in self.pairs:
            lang = Language.objects.get(code=code)

            self.stdout.write(f"Loading {lang.name} audios.")
            with open(f"data/commonvoice/{code}/clips.tsv") as f:
                reader = csv.reader(f, delimiter="\t")
                for i, (path, text) in self.tqdm(enumerate(reader)):
                    sent = Sentence(lang=lang, text=text)
                    sent.audio.name = path
                    sent.save()

        self.stdout.write(self.style.SUCCESS("Audios loaded."))
