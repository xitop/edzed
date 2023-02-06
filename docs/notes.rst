===========
About edzed
===========

The project:

- The name was derived from "**E**\vent **D**\riven **ZE**\ro **D**\elay circuit
  simulator".
- ``edzed`` was written by Vlado Potisk, a software developer from Slovakia.
- Any help with the documentation is appreciated, especially with the English language
  and grammar.
- Release numbering scheme is date based: ``year-2000.month.day`` (PEP-440 compliant).

The development:

- We may make backward incompatible changes, but we will provide a transitory period
  of at least three months if possible.
- The documentation will contain notes about added or changed features for a period
  of at least twelve months.
- We will reject requests to add new blocks except for really useful general purpose blocks
  with functionality not easily obtainable with existing blocks.
  If you have created a special purpose block or block collection, please
  create a separate library.

The code:

- PEP-8 standard with line length limit 96 chars.
- Type hints (annotations) are added for documentation purposes only.
- Information presented in the docs is not duplicated in docstrings.
- Unit tests *are not* good examples of proper usage!

Known problems:

- As always, there are probably bugs.
- The unit tests that checks proper timing may fail on heavily loaded systems.
  Please repeat failed tests.
