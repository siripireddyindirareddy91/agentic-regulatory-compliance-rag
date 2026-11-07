from contextlib import contextmanager
from .models import URL
@contextmanager
def saver():
    if URL.startswith('postgresql'):
        from langgraph.checkpoint.postgres import PostgresSaver
        with PostgresSaver.from_conn_string(URL.replace('postgresql+psycopg://','postgresql://')) as checkpoint:
            checkpoint.setup();yield checkpoint
    else:
        from langgraph.checkpoint.sqlite import SqliteSaver
        path=URL.replace('sqlite:///','',1)+'.checkpoints'
        with SqliteSaver.from_conn_string(path) as checkpoint:yield checkpoint
