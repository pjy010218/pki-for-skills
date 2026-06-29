"""
ABC Checksum Mathematics (Mean, Covariance, Mahalanobis Distance).
"""
import numpy as np


def compute_distributional_checksum(embeddings: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Compute the mean vector and covariance matrix from a set of trace embeddings."""
    if not embeddings:
        raise ValueError("Cannot compute ABC on empty embeddings list.")
    
    # X shape: (N_samples, n_features)
    X = np.vstack(embeddings)
    
    mu = np.mean(X, axis=0)
    
    # If there's only one sample, covariance is 0
    if X.shape[0] == 1:
        sigma = np.zeros((X.shape[1], X.shape[1]))
    else:
        # rowvar=False means columns are variables
        sigma = np.cov(X, rowvar=False)
        
    return mu, sigma


def verify_abc_distance(
    trace_embedding: np.ndarray, 
    mu: np.ndarray, 
    sigma: np.ndarray, 
    threshold: float
) -> tuple[bool, float]:
    """
    Verify a single execution trace against the ABC matrices using Mahalanobis distance.
    Returns (is_valid, distance).
    """
    import scipy.linalg

    delta = trace_embedding - mu
    
    # Add a small epsilon to the diagonal to make the covariance matrix invertible
    # if it's perfectly singular (e.g. from highly deterministic identical traces).
    eps = 1e-6
    sigma_reg = sigma + np.eye(sigma.shape[0]) * eps
    
    # Mahalanobis distance: sqrt((x-mu)^T * Sigma^-1 * (x-mu))
    try:
        inv_sigma_delta = scipy.linalg.solve(sigma_reg, delta, assume_a='pos')
        dist_sq = np.dot(delta, inv_sigma_delta)
        dist = np.sqrt(max(0.0, dist_sq))
    except np.linalg.LinAlgError:
        # Fallback if matrix is completely singular despite regularization
        dist = float('inf')
        
    return dist < threshold, dist
