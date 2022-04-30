from random import randint

# I don't know probability that well, so imma just admit I got this code from here:
# https://stackoverflow.com/a/14992648
#
# weightValPairs must be sorted first for it to work. 
# The object must also contain an integer property called weight!
def weighted_random_list(weightValPairs, count: int):
    total = sum(pair.weight for pair in weightValPairs)
    retVals = []
    for i in range(count):
        rand = randint(1, total)
        for val in weightValPairs:
            rand -= val.weight
            if rand <= 0: retVals.append(val)

    return retVals

# weightValPair must be a list of tuples, where
# index 0 or each tuple is an integer specifying the weight of the result.
def weighted_random(weightValPairs):
    total = sum(pair[0]for pair in weightValPairs)
    
    rand = randint(1, total)
    for val in weightValPairs:
        rand -= val.weight
        if rand <= 0: return val

    # This should never happen if function is used properly.
    return None