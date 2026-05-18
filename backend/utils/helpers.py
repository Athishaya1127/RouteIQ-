def min_max_normalize(matrix):
    """
    Min-Max normalize a 2D matrix so all values are between 0 and 1.
    If the max and min are the same, returns a zero matrix.
    """
    if not matrix or not matrix[0]:
        return matrix
    
    flat = [val for row in matrix for val in row if val is not None]
    if not flat:
        return matrix
        
    min_val = min(flat)
    max_val = max(flat)
    
    range_val = max_val - min_val
    if range_val == 0:
        return [[0.0 for _ in row] for row in matrix]
        
    return [
        [((val - min_val) / range_val) if val is not None else 0.0 for val in row]
        for row in matrix
    ]
