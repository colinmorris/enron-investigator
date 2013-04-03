__author__ = 'colin'

import struct
import os
import sys
import logging
import string

# We're using short ints or whatever they're called. I'm not a C programmer.
POINTER_SIZE = 4

class PrefixTreeNode(object):
    """A node in an in-memory prefix tree
    """

    def __init__(self, char=None):
        """char is None iff this is the root of a tree.
        """
        self.char = char
        self.root = char is None
        # Map from chars to children
        self.children = {}
        # We assume we're not a word ending unless we're told otherwise
        self.terminal = False
        # The offset into the file that this node will live at. This is set externally.
        self.byte_offset = None

    def make_child(self, char):
        """Return the child of this node labelled with the given character.
         Make one if none exists.
         """
        if char not in self.children:
            self.children[char] = PrefixTreeNode(char)

        return self.children[char]

    def pack(self, first_empty_position):
        """first_empty_position: the first index into the file that hasn't been claimed
            by any node

        Returns (bytestring, next_empty_position, queue)
            bytestring : the byte repr of this node
            next_empty_position : the next position we can write a node to
            queue : list of nodes that are due to be written to the file, in order
                    it's important that these are written in the given order, and
                    that nothing is written to the file before the queue is exhausted


        """
        res = ''
        size = self.sizeof()
        if self.byte_offset is None:
            # Then this is the root
            first_empty_position += size
        res += struct.pack('i', size)
        logging.debug("Node with char %s has size %d" % (self.char, self.sizeof()))
        assert self.char is None or \
               isinstance(self.char, str), "No unicode allowed! Char is type " + str(type(self.char))

        # First two fields aren't stored for the root
        if not self.root:
            res += self.char
            res += 't' if self.terminal else 'f'

        node_queue = []
        for child in self.children.itervalues():
            if child.byte_offset is None:
                child.byte_offset = first_empty_position
                logging.debug("Setting node with char %s to offset %d" % (child.char, first_empty_position))
                first_empty_position += child.sizeof()
                node_queue.append(child)

            res += struct.pack('i', child.byte_offset)

        assert len(res) == self.sizeof()
        return res, first_empty_position, node_queue

    def walk(self):
        yield self
        for kid in self.children.itervalues():
            for node in kid.walk():
                yield node

    def sizeof(self):
        """The size of this node's packed representation, in bytes.
        """
        return len(self.children)*POINTER_SIZE + (2 if not self.root else 0) + 4
        #           ^ Size of kids             ^ char and term flag            ^ record size

    def pretty_subtree(self, whitespace=''):
        """Return a pretty (YMMV) ascii representation of the subtree rooted at
        this node.
        """
        res = whitespace + str(self.char) + '\n'
        for child in self.children.itervalues():
            res += child.pretty_subtree(whitespace+'\t')

        return res

    
class PrefixTreeBuilder(object):
    """This will be run offline to build the file that will be used on
    the mobile device.
    """

    def __init__(self):
        self.root = PrefixTreeNode()
        
    def load_directory(self, dirname):
        """Load all the text files in the directory with the given name, exploring
        recursively.
        """
        #for dirpath, dirnames. filenames in os.walk(dirname):
        nfiles = 0
        for thing in os.walk(dirname):
            (dirpath, dirnames, filenames) = thing
            for fname in filenames:
                path = os.path.join(dirpath, fname)
                f = open(path)
                self.file_augment(f)
                f.close()
                nfiles += 1

                if nfiles % 1000 == 0:
                    print "Processed %d emails" % (nfiles)

        
    def word_augment(self, word):
        """Augment this tree with the given word, creating any necessary new nodes
        on the path from the root to the end of the word.
        """
        currnode = self.root
        for char in word:
            currnode = currnode.make_child(char)
            
        currnode.terminal = True
        
    def file_augment(self, email_file):
        """Augment this tree with all the tokens in the given email file.
        """
        for line in email_file:
            # TODO: Should have a method responsible for tokenizing, normalizing, and
            # filtering words
            for word in line.split(): # TODO: Better tokenization?
                if len(word) > 16:
                    word = word[:16]
                # Skip things that don't look like words
                if not any([char in string.letters for char in word]):
                    continue
                self.word_augment(word)
                
    def write(self, f):
        """Write this tree to an indexed file.

        In effect, this ended up being a a breadth-first traversal of the tree.
        """
        offset = 0

        node_queue = [self.root]
        while node_queue:
            node = node_queue.pop(0) # This is really slow, haha
            (bytestring, offset, morenodes) = node.pack(offset)
            f.write(bytestring)
            node_queue += morenodes

        return f

    def walk(self):
        return self.root.walk()

    def __str__(self):
        return self.root.pretty_subtree()




def build_tree(rootdir, out_fname):
    builder = PrefixTreeBuilder()
    builder.load_directory(rootdir)
    f = open(out_fname, 'w')
    builder.write(f)
    f.close()
    return builder

if __name__ == '__main__':
    log = logging.getLogger()
    #log.setLevel('DEBUG')
    if len(sys.argv) < 3:
        print "USAGE: indexbuilder.py rootdir outfile"
        sys.exit(1)

    root = sys.argv[1]
    out = sys.argv[2]
    build_tree(root, out)
