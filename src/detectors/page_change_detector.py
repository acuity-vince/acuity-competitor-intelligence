import difflib

def relevant_change(previous: str, current: str, terms: list[str]) -> dict:
    if previous == current: return {"changed":False,"added":"","removed":"","relevant":False}
    diff=list(difflib.ndiff(previous.split(),current.split()))
    added=" ".join(x[2:] for x in diff if x.startswith('+ '))
    removed=" ".join(x[2:] for x in diff if x.startswith('- '))
    term_changed=any(t.lower() in (added+' '+removed).lower() for t in terms)
    return {"changed":True,"added":added,"removed":removed,"relevant":term_changed}

