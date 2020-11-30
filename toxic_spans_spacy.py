# -*- coding: utf-8 -*-
"""toxic_spans_spacy.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1PXDRIUrrMQdy3XfXkQolpWunjiYmZnFu

# Import
"""
# Commented out IPython magic to ensure Python compatibility.



# Lint as: python3
"""Example tagging for Toxic Spans based on Spacy.
Requires:
  pip install spacy sklearn
Install models:
  python -m spacy download en_core_web_sm
"""

import argparse
import ast
import csv
import random
import statistics
import sys

import sklearn
import spacy

sys.path.append('../evaluation')
#import semeval2021
from toxic_spans.evaluation.semeval2021 import f1
from toxic_spans.evaluation import fix_spans

"""# Pre-Processing"""

def spans_to_ents(doc, spans, label):
  """Converts span indicies into spacy entity labels."""
  started = False
  left, right, ents = 0, 0, []
  for x in doc:
    if x.pos_ == 'SPACE':
      continue
    if spans.intersection(set(range(x.idx, x.idx + len(x.text)))):
      if not started:
        left, started = x.idx, True
      right = x.idx + len(x.text)
    elif started:
      ents.append((left, right, label))
      started = False
  if started:
    ents.append((left, right, label))
  return ents


def read_datafile(filename):
  """Reads csv file with python span list and text."""
  data = []
  with open(filename) as csvfile:
    reader = csv.DictReader(csvfile)
    count = 0
    for row in reader:
      fixed = fix_spans.fix_spans(
          ast.literal_eval(row['spans']), row['text'])
      data.append((fixed, row['text']))
  return data
#nlp = spacy.load("en_core_web_sm")  
#doc = nlp(text)
#spans_to_ents(doc, set(spans), 'TOXIC')

'''
def spans_to_text(text, span): ## pass in text and span
  text = text[span[0]:span[1]+1]
  return text
'''

def to_lowercase(dataset):
    for columns in dataset.columns:
        dataset[columns] = dataset[columns].str.lower() 
    return dataset

def get_args():
    parser = argparse.ArgumentParser("Spacy ner-based model")
    parser.add_argument("--noun_chunks",  help="boolean indicating whether to include noun_chunks in model",
                        action="store_true", default=False)
    parser.add_argument("--fixed_embeddings", help="boolean indicating whether to fix the embeddings (True) or update them during training", default=False)
    parser.add_argument("--max_train_sents", type=int, help="Maximum number of train sentences",  default=1000000)
    parser.add_argument("--num_iters", type=int, help="Number of training iterations", default=2)
    parser.add_argument("--all_lower", help="boolean indicating whether to test and train on lowercase data", default = False)
    args = parser.parse_args()
    print(args)
    return args



"""# Train"""

def main():
  args = get_args()  
    
  """Train and eval a spacy named entity tagger for toxic spans."""
  # Read training data
  print('loading training data')
  train = read_datafile('../toxic_spans/data/tsd_train.csv')

  # Read trial data for test.
  print('loading test data')
  test = read_datafile('/toxic_spans/data/tsd_trial.csv')

  # Lowercase data if all_lower is true
  if args.all_lower:
    train = to_lowercase(train)
    test = to_lowercase(test)

  # Convert training data to Spacy Entities
  nlp = spacy.load("en_core_web_sm")

  print('preparing training data')
  training_data = []
  for n, (spans, text) in enumerate(train):
    doc = nlp(text)
    ents = spans_to_ents(doc, set(spans), 'TOXIC')
    if len(training_data) < int(args.max_train_sents):
        training_data.append((doc.text, {'entities': ents}))
    
  print("Number of training examples is: %d" % len(training_data))

  toxic_tagging = spacy.blank('en')
  toxic_tagging.vocab.strings.add('TOXIC')
  ner = nlp.create_pipe("ner")
  ner.add_label('TOXIC')
  toxic_tagging.add_pipe(ner, last=True)

  if args.noun_chunks:
        merge_nps = nlp.create_pipe("merge_noun_chunks")
        toxic_tagging.add_pipe(merge_nps)
  print(toxic_tagging.pipe_names)

  pipe_exceptions = ["ner", "trf_wordpiecer", "merge_noun_chunks"]
  if not args.fixed_embeddings:
    pipe_exceptions.append("trf_tok2vec")

  unaffected_pipes = [
      pipe for pipe in toxic_tagging.pipe_names
      if pipe not in pipe_exceptions]
  

  print('training')
  with toxic_tagging.disable_pipes(*unaffected_pipes):
    toxic_tagging.begin_training()
    for iteration in range(args.num_iters): #CHANGED FROM 30 
      random.shuffle(training_data)
      losses = {}
      batches = spacy.util.minibatch(
          training_data, size=spacy.util.compounding(
              4.0, 32.0, 1.001))
      for batch in batches:
        texts, annotations = zip(*batch)
        toxic_tagging.update(texts, annotations, drop=0.5, losses=losses)
      print("Losses", losses)

  # Score on trial data.
  print('evaluation')
  scores = []
  for spans, text in test:
    pred_spans = []
    #doc is the sentence we are passing to get tagged
    print("LOWERCASE TESTING SENTENCE", text)
    doc = toxic_tagging(text)
    #ent are the words that were tagged as toxic in the sentence
    for ent in doc.ents:
      pred_spans.extend(range(ent.start_char, ent.start_char + len(ent.text)))
    score = f1(pred_spans, spans)
    scores.append(score)
  print('avg F1 %g' % statistics.mean(scores))


if __name__ == '__main__':
  main()

