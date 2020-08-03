#!/usr/bin/env python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-

import sys

# Lokálisan telepítve az emtsv-t az első-t kell kikommentezni és a megfelelő get_lemmas()-t,
# Dockert használva pedig a második sort és a megfelelő get_lemmas()-t.
# from emtsv import build_pipeline, tools, presets, jnius_config, singleton_store_factory
import requests

from bs4 import BeautifulSoup
from gensim.models import KeyedVectors

KEYWORDS = {'alma', 'körte', 'dinnye', 'szöveg', 'kép', 'festmény', 'szobor'}  # Ezek a kategóriák
R = 0.6  # 0.6 fölötti hasonlóság.
VECTOR_MODEL = KeyedVectors.load('data/glove-hu_152.gensim')  # Ez a model
INPUT_FILE_NAME = 'input.xml'
OUTPUT_FILE_NAME = 'output.xml'


def create_wordset_mapping():
    """
    10-15 előre meghatározott kulcsszó -> ezekből csinálunk szóbokrokat és a bokorhoz hozzárendeljük a szavakat
    """
    inv_word_sets = {}
    for k in KEYWORDS:
        word_set = set()
        for w, s in VECTOR_MODEL.most_similar(k):
            if s > R:
                word_set.add(w)
        inv_word_sets[frozenset(word_set)] = k
    return inv_word_sets


"""
def get_lemmas(input_data, singleton_store=singleton_store_factory()):
    # Lokális telepítés esetén használandó verzió
    # Szöveg megy be, lemma lista jön ki.
    # A második paraméterrel nem kell foglalkozni, a gyorsítást szolgálja ismételt hívás esetén. Jó defaultnak.
    jnius_config.classpath_show_warning = False
    out_iter = build_pipeline(input_data, ['tok', 'morph', 'pos'], tools, presets, singleton_store=singleton_store)
    lemma_list = e_magyar_output_to_lemma_list(out_iter)
    return lemma_list
"""


def get_lemmas(input_data):
    # Dockeres telepítés esetén használandó verzió
    # Szöveg megy be, lemma lista jön ki.
    r = requests.post('http://emtsv.elte-dh.hu:5000/tok/morph/pos', data={'text': input_data})
    if r.status_code != 200:
        print(f'ERROR: something happened with the request: {r.status_code} {r.text}', file=sys.stderr)
        exit(1)
    out_iter = iter(r.text.split('\n'))
    lemma_list = e_magyar_output_to_lemma_list(out_iter)
    return lemma_list


def e_magyar_output_to_lemma_list(out_iter):
    next(out_iter)
    lemma_list = []
    for tok in out_iter:
        if len(tok) > 1:
            form, wsafter, morph, lemma, pos = tok.split('\t')
            lemma_list.append(lemma)
    return lemma_list


def tags_to_lemmas(inp_lemmas, mapping):
    """
    Az összes szót (mindegyiket csak egyszer) megnézzük az összes szóbokorban, ha benne van, akkor hozzáadjuk a tag-et.
    """
    tags = set()
    for lemma in set(inp_lemmas):  # A többször elfőforduló szavakat is csak egszer vesszük
        for words_set, tag in mapping.items():
            if lemma in words_set:
                tags.add(tag)
    return tags


def main():
    tag_mapping = create_wordset_mapping()
    with open(INPUT_FILE_NAME, 'rb') as inp_fh:
        bs_xml = BeautifulSoup(inp_fh, 'lxml-xml')

    for record in bs_xml.find_all('record'):  # Az összes rekordra
        tags_for_record = set()
        for parag in record.find_all('descriptions'):
            for cont_tag_name in ('title', 'text'):
                for cont_tag in parag.find_all(cont_tag_name):
                    lemmas = get_lemmas(str(cont_tag.text) + '\n')  # A string újsorral kell, hogy végződjön!
                    tags_for_record |= tags_to_lemmas(lemmas, tag_mapping)
        if record.find('tags') is None:
            new_tag = bs_xml.new_tag('tags')
            record.append(new_tag)
        for tag in sorted(tags_for_record):
            new_tag = bs_xml.new_tag('tag', attrs={'id': tag})
            record.tags.append(new_tag)
    with open(OUTPUT_FILE_NAME, 'w', encoding='UTF-8') as output_fh:
        print(bs_xml.prettify(), file=output_fh)


if __name__ == '__main__':
    main()
