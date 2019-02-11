import logging
import os
import shutil
import threading
import time

import docker
from django.conf import settings


logger = logging.getLogger(__name__)

CONTAINERS = None

lock = threading.Lock()



def create_container(name):
    return docker.from_env().containers.run(
        settings.DOCKER_IMAGE,
        detach=True,
        environment=settings.DOCKER_ENV_VAR,
        auto_remove=True,
        tty=True,
        cpuset_cpus=settings.DOCKER_CPUSET_CPUS,
        mem_limit=settings.DOCKER_MEM_LIMIT,
        memswap_limit=settings.DOCKER_MEMSWAP_LIMIT,
        network_mode="none",
        network_disabled=True,
        volumes={
            os.path.join(settings.DOCKER_VOLUME_HOST, name): {
                "bind": settings.DOCKER_VOLUME_CONTAINER,
                "mode": "rw",
            },
        }
    )



class ContainerWrapper:
    """Wrap a docker container to store some data."""
    
    
    def __init__(self, name, index, available=True):
        path = os.path.join(settings.DOCKER_VOLUME_HOST, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        os.makedirs(path)
        
        self.name = name
        self.container = create_container(name)
        self.index = index
        self.available = available
        self.used_since = 0
        self.to_delete = False
        self.envpath = os.path.join(settings.DOCKER_VOLUME_HOST, self.name)
        self._get_default_file()
    
    
    def _get_default_file(self):
        """Copy every files and directory in DOCKER_DEFAULT_FILES into container environement."""
        for item in os.listdir(settings.DOCKER_DEFAULT_FILES):
            s = os.path.join(settings.DOCKER_DEFAULT_FILES, item)
            d = os.path.join(self.envpath, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
    
    
    @property
    def need_reset(self):
        """Return True if the container need to be reset, False otherwise."""
        return self.container.status not in ["running", "restarting", "created"] or self.to_delete
    
    
    @staticmethod
    def acquire():
        """Return the first available container, None if none were available."""
        global CONTAINERS
        
        lock.acquire()
        
        cw = next((c for c in CONTAINERS if c.available), None)
        if cw is not None:
            CONTAINERS[cw.index].available = False
            CONTAINERS[cw.index].used_since = time.time()
            logger.info("Acquiring container '%s' of id '%d'" % (cw.name, cw.index))
        
        lock.release()
        
        return cw
    
    
    def release(self):
        """Release this container."""
        global CONTAINERS
        
        if os.path.isdir(self.envpath):
            self.container.exec_run(["/bin/sh", "-c", "rm * -Rf"])
            shutil.rmtree(self.envpath)
        os.makedirs(self.envpath)
        self._get_default_file()
        self.container.restart()
        
        with lock:
            CONTAINERS[self.index].available = True
        logger.info("Releasing container '%s' of id '%d'" % (self.name, self.index))
    
    
    @classmethod
    def refresh_containers(cls):
        """Check that each container are either running, restarting or being created. Reset them if
        this is not the case."""
        global CONTAINERS
        
        lock.acquire()
        
        for i in range(settings.DOCKER_COUNT):
            try:
                CONTAINERS[i].reload()
            except docker.errors.DockerException:
                CONTAINERS[i].to_delete = True
        
        for c in CONTAINERS:
            if not c.need_reset:
                continue
            
            logger.info("Restarting container '%s' of id '%d'" % (c.name, c.index))
            CONTAINERS[c.index].available = False
            threading.Thread(target=c._reset).start()
        
        lock.release()



def initialise_container():
    """Called by settings.py to initialize containers at server launch."""
    global CONTAINERS
    
    lock.acquire()
    
    time.sleep(0.5)
    # Kill stopped container created from DOCKER_IMAGE
    logger.info("Purging existing stopped containers using image : %s." % settings.DOCKER_IMAGE)
    logger.info("Killed stopped container : %s." % str(docker.from_env().containers.prune()))
    
    # Deleting running container created from DOCKER_IMAGE
    CONTAINERS = []
    for c in docker.from_env().containers.list({"ancestor": settings.DOCKER_IMAGE}):
        logger.info("Killing container %s." % repr(c))
        c.kill()
        logger.info("Container %s killed." % repr(c))
    
    # Purging any existing container environment.
    logger.info("Purging any existing container environment.")
    if os.path.isdir(settings.DOCKER_VOLUME_HOST):
        shutil.rmtree(settings.DOCKER_VOLUME_HOST)
    
    # Create containers.
    logger.info("Initializing containers.")
    for i in range(settings.DOCKER_COUNT):
        CONTAINERS.append(ContainerWrapper("c%d" % i, i))
        logger.info("Container %d/%d initialized." % (i, settings.DOCKER_COUNT))
    logger.info("Containers initialized.")
    
    lock.release()
