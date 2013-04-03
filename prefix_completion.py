"""
Uses an index of the kind built by indexbuilder.py to suggest words that follow
a particular prefix.
"""

__author__ = 'colin'

from indexbuilder import POINTER_SIZE
import struct
import sys
import logging

class NoSuchWordException(Exception):
    pass

class NoSuchChildException(Exception):
    pass

class PrefixNode(object):
    """A node in a LightPrefixTree
    """

    def __init__(self, char, f, terminal, kids):
        self.char = char
        self.f = f
        self.terminal = terminal
        # An iterable of indices where we can find this node's children
        self.kids = kids
        self.root = char is None

    @staticmethod
    def from_index(f, index, root=False):
        """Given an index file of the kind built by indexbuilder.py, and an
        offset into that file, return the node that begins at that index.
        """
        f.seek(index)
        logging.debug("Sought to index %d" % (index))
        size = struct.unpack('i', f.read(POINTER_SIZE))[0]
        if size > 100:
            logging.warning("That sure is a big node...")
        remaining_bytes = size - POINTER_SIZE
        if not root:
            char = f.read(1)
            terminal = f.read(1) == 't'
            remaining_bytes -= 2
        else:
            char = None
            # Wouldn't it be cool if the empty string was a word in the dictionary?
            # I wonder what it would mean.
            terminal = False

        children = set([]) # Set of indices of child nodes
        while remaining_bytes > 0:
            try:
                child_pointer = struct.unpack('i', f.read(POINTER_SIZE))
            except struct.error:
                logging.critical("Pointers got messed up. Have %d remaining bytes on char %s at index %d" \
                 % (remaining_bytes, char, index))
                raise
            remaining_bytes -= POINTER_SIZE
            children.add(child_pointer[0])

        assert remaining_bytes == 0, "Something went wrong. Didn't get a clean read."

        return PrefixNode(char, f, terminal, children)

    def get_child(self, char):
        for child in self.children():
            if child.char == char:
                return child

        raise NoSuchChildException()

    def children(self):
        for offset in self.kids:
            yield self.from_index(self.f, offset)

    def word_postfixes(self):
        """Return all postfixes beginning with and including this node that
        form words.
        """
        if self.terminal:
            yield self.char

        for child in self.children():
            for postpostfix in child.word_postfixes():
                yield self.char + postpostfix

    def words(self, prefix):
        """A convenience function to return all words that have this node on their
         path. Prefix must be the string formed by joining the chars of all nodes between
         this node and the root (exclusive).
         """
        for postfix in self.word_postfixes():
            yield prefix + postfix

    def pretty_subtree(self, whitespace=''):
        res = whitespace + str(self.char) + '\n'
        for child in self.children():
            res += child.pretty_subtree(whitespace+'\t')

        return res



class LightPrefixTree(object):
    """Much like the prefix tree defined in indexbuilder.py, but having a
    smaller memory footprint.
    """

    def __init__(self, f):
        self.f = f
        self.root = self._load_root()

    def _load_root(self):
        return PrefixNode.from_index(self.f, 0, True)

    def suggest_words(self, prefix):
        # TODO: This has performance implications for very small prefixes
        # Possible sol'n: Optionally limit results to a particular number (e.g. 5) and break the tree traversal then

        try:
            prefix_subtree = self.get_subtree(prefix)
        except NoSuchWordException:
            return
        for word in prefix_subtree.words(prefix[:-1]):
            yield word

    def get_subtree(self, prefix):
        curr_node = self.root
        for char in prefix:
            try:
                curr_node = curr_node.get_child(char)
            except NoSuchChildException:
                raise NoSuchWordException
        return curr_node

    def __str__(self):
        # Not recommended for production use!
        return self.root.pretty_subtree()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "USAGE: prefix_completion.py indexfile"
        sys.exit(1)

    log = logging.getLogger()
    #log.setLevel('DEBUG')
    index_fname = sys.argv[1]
    f = open(index_fname)
    tree = LightPrefixTree(f)
    #print(tree)
