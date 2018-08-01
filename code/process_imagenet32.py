import os, argparse
import numpy as np
import pickle

parser = argparse.ArgumentParser(description='Process ImageNet32')
parser.add_argument('-d','--data',   help='Directory containing batches',
        type=str, required=True)
opt = parser.parse_args()

class PCA(object):
    def __init__(self, D, n_components):
        self.n_components = n_components
        self.U, self.S, self.m = self.fit(D, n_components)

    def fit(self, D, n_components):
        """
        The computation works as follows:
        The covariance is C = 1/(n-1) * D * D.T
        The eigendecomp of C is: C = V Sigma V.T
        Let Y = 1/sqrt(n-1) * D
        Let U S V = svd(Y),
        Then the columns of U are the eigenvectors of:
        Y * Y.T = C
        And the singular values S are the sqrts of the eigenvalues of C
        We can apply PCA by multiplying by U.T
        """

        # We require scaled, zero-mean data to SVD,
        # But we don't want to copy or modify user data
        m = np.mean(D, axis=1)[:, np.newaxis]
        D -= m
        D *= 1.0 / np.sqrt(D.shape[1] - 1)
        U, S, V = np.linalg.svd(D, full_matrices=False)
        D *= np.sqrt(D.shape[1] - 1)
        D += m
        return U[:, :n_components], S[:n_components], m

    def transform(self, D, whiten=False, ZCA=False,
                  regularizer=10 ** (-5)):
        """
        We want to whiten, which can be done by multiplying by Sigma^(-1/2) U.T
        Any orthogonal transformation of this is also white,
        and when ZCA=True we choose:
         U Sigma^(-1/2) U.T
        """
        if whiten:
            # Compute Sigma^(-1/2) = S^-1,
            # with smoothing for numerical stability
            Sinv = 1.0 / (self.S + regularizer)

            if ZCA:
                # The ZCA whitening matrix
                W = np.dot(self.U,
                           np.dot(np.diag(Sinv),
                                  self.U.T))
            else:
                # The whitening matrix
                W = np.dot(np.diag(Sinv), self.U.T)

        else:
            W = self.U.T

        # Transform
        return np.dot(W, D - self.m)


def proc_imagenet32(loc):
    def _load_batch(fn):
        fo = open(fn, 'rb')
        d = pickle.load(fo)
        fo.close()
        return d['data'].reshape(-1, 3, 32, 32), d['labels']

    def normalize(data, eps=1e-8):
        data -= data.mean(axis=(1, 2, 3), keepdims=True)
        std = np.sqrt(data.var(axis=(1, 2, 3), ddof=1, keepdims=True))
        std[std < eps] = 1.
        data /= std
        return data

    proc_loc = 'proc'
    if os.path.exists(proc_loc):
        print('Found existing proc, delete the proc folder if you want to run again')
        return
    os.mkdir(proc_loc)

    print('[Loading]')
    train_fns = [os.path.join(loc, 'train_data_batch_' + str(i)) for i in range(1, 11)]
    train_batches = [_load_batch(fn) for fn in train_fns]
    test_batch = _load_batch(os.path.join(loc, 'val_data'))

    tx = np.vstack([train_batches[i][0] for i in range(10)]).astype('float32')
    ty = []
    for i in range(10):
        ty += train_batches[i][1]
    ty = np.array(ty)-1
    vx, vy = test_batch[0].astype('float32'), np.array(test_batch[1])-1

    tx, vx = normalize(tx), normalize(vx)
    txf, vxf = tx.reshape(tx.shape[0], -1).T, vx.reshape(vx.shape[0], -1).T
    np.savez(os.path.join(proc_loc, 'imagenet32-train.npz'), data=tx, labels=ty)
    np.savez(os.path.join(proc_loc, 'imagenet32-test.npz'), data=vx, labels=vy)
    sys.exit(0)

    print('[Whitening]')
    pca = PCA(D=txf, n_components=txf.shape[1])
    tx = pca.transform(D=txf, whiten=True, ZCA=True).T.reshape(tx.shape)
    vx = pca.transform(D=vxf, whiten=True, ZCA=True).T.reshape(vx.shape)

    print('[Saving]')
    np.savez(os.path.join(proc_loc, 'imagenet32-train-proc.npz'), data=tx, labels=ty)
    np.savez(os.path.join(proc_loc, 'imagenet32-test-proc.npz'), data=vx, labels=vy)
    print('[Finished]')

loc = opt.data
assert os.path.exists(loc), 'loc does not exist: %s' % loc
raw_loc = os.path.join(loc, 'imagenet32')
assert os.path.exists(raw_loc), 'Download ImageNet32'

proc_imagenet32(raw_loc)
