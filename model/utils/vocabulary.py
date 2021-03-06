import os
from collections import Counter, OrderedDict
import random

import torch
import numpy as np

from .augment import *

class Vocab(object):
    def __init__(self, special=[], min_freq=0, max_size=None, lower_case=True,
                 delimiter=None, vocab_file=None):
        self.counter = Counter()
        self.special = special
        self.min_freq = min_freq
        self.max_size = max_size
        self.lower_case = lower_case
        self.delimiter = delimiter
        self.vocab_file = vocab_file

    def tokenize(self, line, add_eos=False, add_double_eos=False):
        line = line.strip()
        # convert to lower case
        if self.lower_case:
            line = line.lower()

        # empty delimiter '' will evaluate False
        if self.delimiter == '':
            symbols = line
        else:
            symbols = line.split(self.delimiter)

        if add_double_eos: # lm1b
            return ['<S>'] + symbols + ['<S>']
        elif add_eos:
            return symbols + ['<eos>']
        else:
            return symbols

    def count_file(self, path, verbose=False, add_eos=False):
        if verbose: print('counting file {} ...'.format(path))
        assert os.path.exists(path)

        sents = []
        with open(path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                if verbose and idx > 0 and idx % 500000 == 0:
                    print('    line {}'.format(idx))
                symbols = self.tokenize(line, add_eos=add_eos)
                self.counter.update(symbols)
                sents.append(symbols)

        return sents

    def count_sents(self, sents, verbose=False):
        """
            sents : a list of sentences, each a list of tokenized symbols
        """
        if verbose: print('counting {} sents ...'.format(len(sents)))
        for idx, symbols in enumerate(sents):
            if verbose and idx > 0 and idx % 500000 == 0:
                print('    line {}'.format(idx))
            self.counter.update(symbols)

    def _build_from_file(self, vocab_file):
        self.instag2min = {}
        self.instag2max = {}
        self.idx2sym = []
        self.sym2idx = OrderedDict()
        self.wait_amts = set()
        with open(vocab_file, 'r', encoding='utf-8') as f:
            self.add_symbol('<S>')
            for line in f:
                symb = line.strip().split(',')[-1]
                self.add_symbol(symb)
        #self.unk_idx = self.sym2idx['<UNK>']

    def build_vocab(self):
        if self.vocab_file:
            print('building vocab from {}'.format(self.vocab_file))
            self._build_from_file(self.vocab_file)
            print('final vocab size {}'.format(len(self)))
        else:
            print('building vocab with min_freq={}, max_size={}'.format(
                self.min_freq, self.max_size))
            self.idx2sym = []
            self.sym2idx = OrderedDict()

            for sym in self.special:
                self.add_special(sym)

            for sym, cnt in self.counter.most_common(self.max_size):
                if cnt < self.min_freq: break
                self.add_symbol(sym)

            print('final vocab size {} from {} unique tokens'.format(
                len(self), len(self.counter)))

    def encode_file(self, path, ordered=False, verbose=False, add_eos=True,
            add_double_eos=False,
            augment_transpose=False,
            augment_stretch=False,
            augment_switchp1p2=False,
            augment_selectens=False,
            trim_padding=False):
        if verbose: print('encoding file {} ...'.format(path))
        assert os.path.exists(path)
        encoded = []
        with open(path, 'r', encoding='utf-8') as f:
            events = f.read().strip().splitlines()

            if trim_padding:
                if len(events) > 0 and events[0][:2] == 'WT':
                    events = events[1:]
                if len(events) > 0 and events[-1][:2] == 'WT':
                    events = events[:-1]

            if augment_selectens:
                if np.random.rand() < 0.5:
                    numins = int(np.random.randint(1, 4))
                    ins = ['P1', 'P2', 'TR', 'NO']
                    ens = random.sample(ins, numins)
                    events = nesmdb_select_instruments(events, ens)

            if augment_switchp1p2:
                if np.random.rand() < 0.5:
                    events = nesmdb_switch_pulse(events)

            if augment_transpose:
                transpose_amt = int(np.random.randint(-6, 7))
                events = nesmdb_transpose(events, transpose_amt, self.instag2min, self.instag2max)

            if augment_stretch:
                playback_speed = np.random.uniform(low=0.95, high=1.05)
                events = nesmdb_stretch(events, playback_speed)

            collapsed = [' '.join(events)]
            for idx, line in enumerate(collapsed):
                if verbose and idx > 0 and idx % 500000 == 0:
                    print('    line {}'.format(idx))
                symbols = self.tokenize(line, add_eos=add_eos,
                    add_double_eos=add_double_eos)
                encoded.append(self.convert_to_tensor(symbols))

        if ordered:
            encoded = torch.cat(encoded)

        return encoded

    def encode_sents(self, sents, ordered=False, verbose=False):
        if verbose: print('encoding {} sents ...'.format(len(sents)))
        encoded = []
        for idx, symbols in enumerate(sents):
            if verbose and idx > 0 and idx % 500000 == 0:
                print('    line {}'.format(idx))
            encoded.append(self.convert_to_tensor(symbols))

        if ordered:
            encoded = torch.cat(encoded) # 텐서를 결합

        return encoded

    def add_special(self, sym):
        if sym not in self.sym2idx:
            self.idx2sym.append(sym)
            self.sym2idx[sym] = len(self.idx2sym) - 1
            setattr(self, '{}_idx'.format(sym.strip('<>')), self.sym2idx[sym])

    def add_symbol(self, sym):
        sym_tokens = sym.split('_')

        if sym_tokens[0] == 'WT':
          wait_amt = int(sym.split('_')[1])
          self.wait_amts.add(wait_amt)

        if len(sym_tokens) > 1 and sym_tokens[1] == 'NOTEON':
          instag = sym_tokens[0]
          midi_note = int(sym_tokens[2])

          if instag not in self.instag2min:
            self.instag2min[instag] = midi_note
          if instag not in self.instag2max:
            self.instag2max[instag] = midi_note

          if midi_note < self.instag2min[instag]:
            self.instag2min[instag] = midi_note

          if midi_note > self.instag2max[instag]:
            self.instag2max[instag] = midi_note

        if sym not in self.sym2idx:
            self.idx2sym.append(sym)
            self.sym2idx[sym] = len(self.idx2sym) - 1

    def get_sym(self, idx):
        assert 0 <= idx < len(self), 'Index {} out of range'.format(idx)
        return self.idx2sym[idx]

    def get_idx(self, sym):
        if sym in self.sym2idx:
            return self.sym2idx[sym]
        else:
            assert sym[:2] == 'WT'
            wait_amt = int(sym.split('_')[1])
            closest = min(self.wait_amts, key=lambda x:abs(x - wait_amt))
            return self.sym2idx['WT_{}'.format(closest)]
            # print('encounter unk {}'.format(sym))
            #assert '<eos>' not in sym
            #assert hasattr(self, 'unk_idx')
            #return self.sym2idx.get(sym, self.unk_idx)

    def get_symbols(self, indices):
        return [self.get_sym(idx) for idx in indices]

    def get_indices(self, symbols):
        return [self.get_idx(sym) for sym in symbols]

    def convert_to_tensor(self, symbols):
        return torch.LongTensor(self.get_indices(symbols))

    def convert_to_sent(self, indices, exclude=None):
        if exclude is None:
            return ' '.join([self.get_sym(idx) for idx in indices])
        else:
            return ' '.join([self.get_sym(idx) for idx in indices if idx not in exclude])

    def __len__(self):
        return len(self.idx2sym)
