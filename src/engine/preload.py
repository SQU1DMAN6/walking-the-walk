from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
import pickle
import os
import tempfile
import time
import uuid


_cancel=None


class GenerationCancelled(Exception):pass


def checkpoint():
    if _cancel is not None and _cancel.is_set():raise GenerationCancelled()


def _worker_init(cancel):
    global _cancel
    _cancel=cancel
    if hasattr(os,'nice'):os.nice(5)


def build_world(key,directory):
    from engine.camera import Camera
    from engine.survival import SurvivalRun
    from engine.tutorial import TutorialRun
    started=time.perf_counter();checkpoint()
    is_run,seed,config=key
    level=SurvivalRun(Camera(),seed,config) if is_run else TutorialRun(Camera(),seed)
    file=Path(directory)/(uuid.uuid4().hex+'.world')
    try:
        checkpoint()
        with file.open('wb') as stream:pickle.dump(level,stream,protocol=pickle.HIGHEST_PROTOCOL)
        checkpoint()
        return dict(key=key,path=str(file),seconds=time.perf_counter()-started,bytes=file.stat().st_size)
    except BaseException:
        file.unlink(missing_ok=True)
        raise
    finally:level.world.close()


class WorldPreloader:
    def __init__(self):
        self.directory=tempfile.TemporaryDirectory(prefix='walking-worlds-')
        context=multiprocessing.get_context('spawn')
        self.cancel=context.Event()
        self.executor=ProcessPoolExecutor(max_workers=1,mp_context=context,initializer=_worker_init,initargs=(self.cancel,))
        self.future=self.running=None
        self.targets=();self.priority=None;self.ready={};self.errors={};self.closed=False
        self.interruptions=0

    def request(self,targets,priority):
        self.targets=tuple(key for key in targets if key is not None)
        self.priority=priority
        if self.future and not self.future.done() and (self.running not in self.targets or
                self.running!=priority and priority not in self.ready and priority is not None):
            if not self.cancel.is_set():self.interruptions+=1
            self.cancel.set()

    def poll(self):
        if self.closed:return
        if self.future and self.future.done():
            key=self.running
            try:
                result=self.future.result()
                if key in self.targets:self.ready[key]=result
                else:Path(result['path']).unlink(missing_ok=True)
            except GenerationCancelled:pass
            except Exception as error:self.errors[key]=str(error)
            self.future=self.running=None;self.cancel.clear()
        for key,result in tuple(self.ready.items()):
            if key not in self.targets:
                Path(result['path']).unlink(missing_ok=True);del self.ready[key]
        self.errors={key:error for key,error in self.errors.items() if key in self.targets}
        if self.future is None:
            order=list(dict.fromkeys((self.priority,*self.targets)))
            key=next((key for key in order if key in self.targets and key not in self.ready and key not in self.errors),None)
            if key is not None:
                self.running=key;self.future=self.executor.submit(build_world,key,self.directory.name)

    def take(self,key):
        result=self.ready.pop(key,None)
        if result is None:return None
        file=Path(result['path'])
        try:
            with file.open('rb') as stream:return pickle.load(stream)
        finally:file.unlink(missing_ok=True)

    def close(self):
        if self.closed:return
        self.closed=True;self.cancel.set()
        if self.future:self.future.cancel()
        self.executor.shutdown(wait=True,cancel_futures=True)
        self.ready.clear();self.directory.cleanup()
