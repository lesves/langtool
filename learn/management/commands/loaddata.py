from django.core.management.base import CommandError
from django_tqdm import BaseCommand

from django.db import transaction
from django.db.models import Q

from django.conf import settings

from learn.models import Language, Sentence, Task, Course

from wordfreq import word_frequency
from nltk.tokenize import word_tokenize

import csv
import re


class Command(BaseCommand):
    help = "Load data for selected language pairs (in settings) to the database"

    pairs = settings.LANGTOOL_LANGUAGE_PAIRS

    @transaction.atomic
    def handle(self, *args, **options):
        self.setup_languages()
        self.load_sentences()
        self.load_voice()
        self.create_tasks()
        self.create_courses()

    def setup_languages(self):
        Language.objects.bulk_create([
            Language(code, name, native_name) 
            for code, name, native_name in settings.LANGTOOL_LANGUAGES
        ], ignore_conflicts=True)

    def load_sentences(self):
        for tcode, scode in self.pairs:
            self.stdout.write(f"Loading {scode}-{tcode} sentences.")
            with open(f"data/{scode}-{tcode}.tsv") as f:
                # Skip BOM
                if f.read(1) != "\ufeff":
                    f.seek(0)

                reader = csv.reader(f, delimiter="\t")

                for sent_id, sent_text, trans_id, trans_text in self.tqdm(reader):
                    sent_id = int(sent_id.strip())
                    trans_id = int(trans_id.strip())

                    sent, _ = Sentence.objects.get_or_create(link_id=sent_id, text=sent_text, lang=Language.objects.get(code=scode))
                    trans, _ = Sentence.objects.get_or_create(link_id=trans_id, text=trans_text, lang=Language.objects.get(code=tcode))
                    sent.translations.add(trans)

        self.stdout.write(self.style.SUCCESS("Sentences loaded."))

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

    def create_tasks(self):
        for _, code in self.pairs:
            self.stdout.write(f"Creating tasks for {code}.")

            lang = Language.objects.get(code=code)
            for sent in Sentence.objects.filter(lang=lang):
                _, rarest_idx = min([(wf, i) for i, tok in enumerate(word_tokenize(sent.text, lang.name)) if (wf := word_frequency(tok, "ru")) > 0])
                task = Task.objects.create(sentence=sent, hidden=rarest_idx)

        self.stdout.write(self.style.SUCCESS("Tasks created."))

    def create_courses(self):
        for _, code in self.pairs:
            lang = Language.objects.get(code=code)

            writing = Course.objects.create(lang=lang, name=f"{lang.name} words in context")
            listening = Course.objects.create(lang=lang, name=f"{lang.name} listening")

            writing.tasks.set(Task.objects.filter(sentence__lang=lang, sentence__translations__isnull=False))
            listening.tasks.set(Task.objects.filter(Q(sentence__lang=lang) & ~Q(sentence__audio="")))
