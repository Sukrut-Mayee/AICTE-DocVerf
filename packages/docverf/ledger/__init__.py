"""Hash-chained audit log and blockchain anchoring (TRD §14). May make network calls.

TODO(question): TRD §1 rule 5 says only services/ touch the database, but §14 says `append`
inserts rows atomically. Where does the DB access live (a session passed in, or a service)?
"""
