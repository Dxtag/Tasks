from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Callable, Generator, Generic, Iterable, ParamSpec, TypeVar
from graphlib import TopologicalSorter

T = TypeVar("T")
P = ParamSpec("P")

class ExecutionException(Exception):
    pass

class WorkflowException(Exception):
    pass

class Execution(Generic[P, T]):
    def __init__(self, 
                 func: Callable[P, T],
                 *args: P.args, 
                 **kwargs: P.kwargs
                 ):
        """
        This class should be created by calling Task object. 
        It represents a single execution of a task with given arguments.

        Args:
            func (Callable[P, T]): Function to execute
        """
        self.__func = func
        self.value_args = args
        self.value_kwargs = kwargs
        self.__resolved = False

    def is_resolved(self) -> bool:
        return self.__resolved
    
    @property
    def output(self) -> T:
        if not self.__resolved:
            raise ExecutionException("Result is not resolved yet.")
        return self.__value
    
    def _resolve_dependencies(self):
        resolved_args = [arg.output if isinstance(arg, Execution) else arg for arg in self.value_args]
        resolved_kwargs = {k: v.output if isinstance(v, Execution) else v for k, v in self.value_kwargs.items()}
        return resolved_args, resolved_kwargs

    def run(self):
        if self.__func is None:
            raise ExecutionException("No function to execute.")
        self._resolve_dependencies()
        resolved_args, resolved_kwargs = self._resolve_dependencies()
        self.__value = self.__func(*resolved_args, **resolved_kwargs)
        self.__resolved = True


class Task(Generic[P, T]):
    def __init__(self, 
                    name: str, 
                    func: Callable[P, T],):
        """Task is a wrapper around function that allows to create execution objects with given arguments.

        Args:
            name (str): for future use, currently not used
            func (Callable[P, T]):  function to execute
        """
        if not callable(func):
            raise ValueError("func must be callable.")
        self.name = name
        self.func = func
        
        
    def __call__(self, *args:P.args, **kwargs:P.kwargs) -> Execution[T]:
        """Calling Task creates an Execution object with given arguments.
            Args and Kwarg will be passed to function when execution is run.
        """
        return Execution(self.func, *args, **kwargs)

def task(func: Callable[P, T]) -> Task[P, T]:
    """Decorator for creating Task objects from functions.

    Args:
        func (Callable[P, T]): function to execute

    Returns:
        Task[P, T]: Task object that can be called to create Execution objects
    """
    return Task(func.__name__, func)

class Workflow:

    def __init__(self, lazy_dependencies: bool = True, auto_register_implicit_dependencies: bool = True):
        """ Workflow builds a DAG of tasks and their dependencies. 
            You should add tasks to workflow using add_job, then you can get tasks in order of execution using get_job generator method.
        Args:
            lazy_dependencies (bool, optional): If false you can't add job with dependencie that isn't already in workflow. Defaults to True.
            auto_register_implicit_dependencies (bool, optional): If true, implicit dependencies will be registered automatically. Defaults to True.
        """
        self.__lazy_dependencies = lazy_dependencies
        self.__auto_register_implicit_dependencies = auto_register_implicit_dependencies
        self.jobs : dict[Execution, Iterable[Execution]] = {}


    def get_job(self)->Generator[Execution, None, None]:
        """Returns tasks in order of execution. 
           If auto_register_implicit_dependencies is true, it will register implicit dependencies before returning tasks.

        Yields:
            Generator[Execution, None, None]: Task to execute
        """
        if not self.jobs:
            raise WorkflowException("No jobs in workflow.")
        if self.__auto_register_implicit_dependencies:
            self.register_implicit_dependencies()
        ts = TopologicalSorter(self.jobs)
        jobs = ts.static_order()
        for j in jobs:
            yield j

    def register_implicit_dependencies(self):
        """Registers implicit dependencies. 
           Implicit dependencies are tasks that are not explicitly added to workflow, but are dependencies of tasks that are added to workflow.
        """
        
        while True:
            not_in_workflow = []
            for _, dependencies in self.jobs.items():
                for j in dependencies:
                    if j not in self.jobs:
                        not_in_workflow.append(j)
            if not not_in_workflow:
                break
            for job in not_in_workflow:
                    self.add_job(job)

    def add_job(self, t: Execution):
        """
        Adds task (Execution) to workflow.

        Args:
            t (Execution): task (Execution) to add to workflow

        Raises:
            WorkflowException: If lazy_dependencies is false and there is a dependency that is not in workflow.
        """
        if t in self.jobs:
            return  
        
        self.jobs[t] = []
        
        for arg in t.value_args:
            if isinstance(arg, Execution):
                self.jobs[t].append(arg)
        
        for kwarg in t.value_kwargs.values():
            if isinstance(kwarg, Execution):
                self.jobs[t].append(kwarg)

        if not self.__lazy_dependencies:
            for dep in self.jobs[t]:
                if dep not in self.jobs:
                    raise WorkflowException("Dependency not in workflow.")