from graphlib import CycleError
import pytest
from workflow import Execution, Workflow, ExecutionException, WorkflowException, task

@task
def add(a: int, b: int) -> int:
    return a + b

@task
def multiply(a: int, b: int) -> int:
    return a * b

@task
def identity(x):
    return x

@task
def throws_error():
    raise ValueError("Task failed internally")

@task
def task_return_multiple_values():
    return 1, 2, 3

def test_simple_dependency_resolution():
    """Tasks are executed in the correct order based on their dependencies."""
    w = Workflow()
    e1 = identity(5)
    e2 = add(e1, 10)
    e3 = multiply(e2, 2)
    w.add_job(e3)
    jobs = list(w.get_job())
    assert jobs == [e1, e2, e3]
    for job in jobs:
        job.run()
    assert e3.output == 30

def test_deep_implicit_dependencies():
    """Nested implicit dependencies (Execution inside Execution inside Execution) 
    are resolved correctly without infinite loops."""
    w = Workflow(auto_register_implicit_dependencies=True)
    e1 = identity(5)
    e2 = identity(e1)  
    e3 = identity(e2)  
    w.add_job(e3)
    jobs = list(w.get_job())
    assert jobs == [e1, e2, e3]
    for job in jobs:
        job.run()
    assert e3.output == 5
    
def test_mixed_args_and_kwargs_dependencies():
    """Execution dependencies are discovered whether they are passed as args or kwargs."""
    w = Workflow()
    e_arg = identity(10)
    e_kwarg = identity(2)
    e_root = add(e_arg, b=e_kwarg)
    w.add_job(e_root)
    jobs = list(w.get_job())
    assert e_arg in jobs
    assert e_kwarg in jobs
    assert jobs[-1] == e_root  

def test_strict_dependencies_raises_exception():
    """If lazy_dependencies=False, adding a task with a dependency 
    not already present in the workflow immediately crashes."""
    w = Workflow(lazy_dependencies=False)
    e1 = identity(1)
    e2 = identity(e1)
    with pytest.raises(WorkflowException):
        w.add_job(e2)
    w.add_job(e1)
    w.add_job(e2)  

def test_cyclic_dependency_detection():
    """Circular dependencies are caught by the topological sorter."""
    w = Workflow()
    e1 = identity(1)
    e2 = identity(2)
    w.add_job(e1)
    w.add_job(e2)
    w.jobs[e1].append(e2)
    w.jobs[e2].append(e1)
    with pytest.raises(CycleError):
        list(w.get_job())

def test_duplicate_job_registrations():
    """Adding the exact same execution instance multiple times 
    does not result in duplicate entries in the workflow's job list."""
    w = Workflow()
    e1 = identity(1)
    e2 = identity(e1)
    w.add_job(e2)
    w.add_job(e2)  
    w.add_job(e1)
    jobs = list(w.get_job())
    assert jobs.count(e2) == 1
    assert jobs.count(e1) == 1

def test_task_execution_failure_propagation():
    """Task execution failures are propagated correctly."""
    w = Workflow()
    e_fail = throws_error()
    e_downstream = identity(e_fail)
    w.add_job(e_downstream)
    jobs = list(w.get_job())
    with pytest.raises(ValueError):
        jobs[0].run()
    assert not jobs[0].is_resolved()

    with pytest.raises(ExecutionException):
        jobs[1].run()

def test_lambda_and_closures_as_tasks():
    """Tasks wrapped around closures/lambdas are evaluate properly."""
    factor = 2
    @task
    def dynamic_closure(x):
        return x * factor
    w = Workflow()
    e = dynamic_closure(10)
    w.add_job(e)
    for job in w.get_job():
        job.run()
    assert e.output == 20

def test_independent_executions_from_same_task():
    """Calling the same Task object multiple times returns unique, 
    isolated execution states."""
    t = identity
    e1 = t("first")
    e2 = t("second")
    assert e1 != e2
    assert not e1.is_resolved()
    assert not e2.is_resolved()
    e1.run()
    assert e1.output == "first"
    with pytest.raises(ExecutionException):
        _ = e2.output

def test_task_with_no_function():
    """Creating an Execution with no function should raise an exception."""
    with pytest.raises(ExecutionException):
        e = Execution(None)
        e.run()

def test_task_return_multiple_values():
    """Tasks that return multiple values are handled correctly."""
    w = Workflow()
    e = task_return_multiple_values()
    w.add_job(e)
    for job in w.get_job():
        job.run()
    assert e.output == (1, 2, 3)

def test_task_return_multiple_values2():
    """Tasks that return multiple values are handled correctly."""
    w = Workflow()
    e = task_return_multiple_values()
    w.add_job(e)

    for job in w.get_job():
        job.run()
    assert e.output == (1, 2, 3)

def test_diamond_style_graph():
    """Diamond-shaped dependency graph are handled correctly."""
    w = Workflow()
    m0 = multiply(5, 5)
    a1 = add(m0, 2)
    a2 = add(m0, 4)
    m3 = multiply(a1, a2)
    w.add_job(m3)
    for job in w.get_job():
        job.run()
    assert m3.output == 783


def test_no_jobs_in_workflow():
    """Getting jobs from an empty workflow should raise an exception."""
    w = Workflow()
    with pytest.raises(WorkflowException):
        list(w.get_job())
