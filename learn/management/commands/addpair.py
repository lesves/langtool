from django.core.management.base import CommandError
from django_tqdm import BaseCommand

from django.db import transaction
from django.db.models import Q

from django.conf import settings

from learn.models import Language, Sentence, Word

from multilang import normalize, lemmatize
from wordfreq import word_frequency, zipf_frequency, iter_wordlist

from itertools import islice

from pathlib import Path
import csv
import re


class Command(BaseCommand):
    help = "Add a language pair"

    def add_arguments(self, parser):
        parser.add_argument("source_lang", type=str)
        parser.add_argument("target_lang", type=str)
        parser.add_argument("-w", "--nwords", default=10_000, type=int)
        parser.add_argument("-s", "--nsents", type=int, default=float("inf"))

    @transaction.atomic
    def handle(self, *args, **options):
        self.setup_languages()

        self.source = Language.objects.get(code=options["source_lang"])
        self.target = Language.objects.get(code=options["target_lang"])
        self.nwords = options["nwords"]
        self.nsents = options["nsents"]

        self.course, created = Course.objects.get_or_create(known=self.source, learning=self.target)
        if created:
            raise CommandError(f"Course {self.course} already exists.")

        sent_file = Path("data") / f"{self.target.code}-{self.source.code}.tsv"
        voice_file = Path("data/commonvoice/") / self.target.code / "clips.tsv"

        if not sent_file.exists():
            raise CommandError(f"Could not find all required file: {sent_file}.")

        self.load_sentences(sent_file)

        if voice_file.exists():
            self.load_voice(voice_file)
        else:
            self.stdout.write(self.style.NOTICE("Notice: Voice files not found."))
            
        self.link_words()

    def setup_languages(self):
        Language.objects.bulk_create([
            Language(code, name, native_name) 
            for code, name, native_name in settings.LANGTOOL_LANGUAGES
        ], ignore_conflicts=True)

    def load_sentences(self, sent_file):
        self.stdout.write(f"Loading {sent_file}.")
        with sent_file.open() as f:
            # Skip BOM
            if f.read(1) != "\ufeff":
                f.seek(0)

            reader = csv.reader(f, delimiter="\t")

            for i, (sent_id, sent_text, trans_id, trans_text) in enumerate(self.tqdm(reader)):
                if i >= self.nsents:
                    break

                sent_id = int(sent_id.strip())
                trans_id = int(trans_id.strip())

                trans, _ = Sentence.objects.get_or_create(
                    link_id=trans_id, 
                    text=trans_text, 
                    lang=self.source
                )
                sent, _ = Sentence.objects.get_or_create(
                    link_id=sent_id, 
                    text=sent_text, 
                    lang=self.target
                )
                sent.translations.add(trans)

        self.stdout.write(self.style.SUCCESS("Sentences loaded."))

    def link_words(self):
        self.stdout.write(f"Building words for {self.target}.")

        c = 0

        it = iter_wordlist(self.target.code)

        while c < self.nwords:
            w = next(it)

            if not w.isalpha():
                continue

            lw = lemmatize(w, self.target.code)

            if zipf_frequency(lw, self.target.code) <= 3.0:
                continue

            _, created = Word.objects.get_or_create(
                text=lw, 
                lang=self.target, 
                freq=word_frequency(lw, self.target.code)
            )

            if created:
                c += 1

        self.stdout.write(f"Linking words in {self.target} with sentences.")

        for sent in self.tqdm(Sentence.objects.filter(lang=self.target)):
            for w in sent.tokens:
                try:
                    sent.words.add(Word.objects.get(lang=self.target, text=lemmatize(w, self.target.code)))
                except Word.DoesNotExist:
                    pass

        self.stdout.write(self.style.SUCCESS("Words linked."))

    def load_voice(self, voice_file):
        self.stdout.write(f"Loading {self.target.name} audios.")
        with voice_file.open() as f:
            reader = csv.reader(f, delimiter="\t")
            for i, (path, text) in self.tqdm(enumerate(reader)):
                sent = Sentence(lang=self.target, text=text)
                sent.audio.name = path
                sent.save()

        self.stdout.write(self.style.SUCCESS("Audios loaded."))
