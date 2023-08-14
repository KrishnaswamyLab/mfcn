import numpy as np
import torch_geometric
import os
from pcnn import DATA_DIR

def h(lam,j):
    # lam is a numpy array
    # returns a numpy array
    return g(lam)**(2**(j-1)) - g(lam)**(2**j)

def g(lam):
    return np.exp(-lam)

def calculate_wavelet(eigenval,eigenvec,J, eps):
    dilation = np.arange(1,J+1).tolist()
    wavelet = []
    N = eigenvec.shape[0]
    wavelet.append(np.identity(N) - np.einsum('ik,jk->ij',eigenvec * g(eigenval), eigenvec))
    for dil in dilation:
        wavelet.append(compute_wavelet_filter(eigenvec, eigenval, dil))
    return wavelet, np.einsum('ik,jk->ij', eigenvec * g(eigenval*2**J), eigenvec)

def compute_wavelet_filter(eigenvec, eigenval, j):
    H = np.einsum('ik,jk->ij', eigenvec * h(eigenval, j), eigenvec)
    return H

def weighted_wavelet_transform(wavelet, f, N):
    Wf = [(1/N) * np.matmul(psi, f) for psi in wavelet]
    return Wf

def zero_order_feature(Aj, f, N, norm_list):
    if norm_list == "none":
        F0 = (1/N) * np.matmul(Aj, f).reshape(-1, 1)
    else:
        this_F0 = np.abs(f).reshape(-1, 1)
        F0 = np.sum(np.power(this_F0, norm_list[0]),axis=0).reshape(-1, 1)
        for i in range(1, len(norm_list)):
            F0 = np.vstack((F0, np.sum(np.power(this_F0, norm_list[i]), axis=0).reshape(-1, 1)))
    return F0

def first_order_feature(psi, Wf, Aj, N, norm_list):
    F1 = [(1/N) * np.matmul(Aj, np.abs(ele)) for ele in Wf]
    if norm_list == "none":
        F1 = [(1/N) * np.matmul(Aj, np.abs(ele)) for ele in Wf]
    else:
        this_F1 = np.stack([(1/N) * np.abs(ele) for ele in Wf])
        F1 = np.sum(np.power(this_F1, norm_list[0]),axis=1).reshape(-1, 1)
        for i in range(1, len(norm_list)):
            F1 = np.concatenate((F1, np.sum(np.power(this_F1, norm_list[i]),axis=1).reshape(-1, 1)),1)
    return np.reshape(F1, (-1, 1))

def selected_second_order_feature(psi,Wf,Aj, N, norm_list):
    #only takes j2 > j1
    temp = np.abs(Wf[0:1])
    F2 = (1/N) * np.einsum('ij,aj->ai', psi[1], temp)
    for i in range(2,len(psi)):
        temp = np.abs(Wf[0:i])
        F2 = np.concatenate((F2,(1/N) * np.einsum('ij,aj ->ai',psi[i],temp)),0)
    F2 = np.abs(F2)
    if norm_list == "none":
        F2 = np.reshape(F2, (-1, 1))
    else:
        this_F2 = F2
        F2 = np.sum(np.power(this_F2, norm_list[0]), axis = 1).reshape(-1, 1)
        for i in range(1, len(norm_list)):
            F2 = np.vstack((F2, np.sum(np.power(this_F2, norm_list[i]), axis=1).reshape(-1, 1)))
    return F2.reshape(-1,1)

def generate_feature(psi,Wf,Aj,f, N, norm="none"):
    #with zero order, first order and second order features
    F0 = zero_order_feature(Aj, f, N, norm)
    F1 = first_order_feature(psi,Wf,Aj, N, norm)
    F2 = selected_second_order_feature(psi,Wf,Aj, N, norm)
    F = np.concatenate((F0,F1),axis=0)
    F = np.concatenate((F,F2),axis=0)
    return F

def compute_all_features(eigenval, eigenvec, signal, eps, N, norm_list, J):
    
    feature = []
    #psi,Aj = calculate_wavelet(eigenval,eigenvec,J, eps)
    #Wf = weighted_wavelet_transform(psi,signal, N)
    #features = generate_feature(psi, Wf, Aj, signal, N, norm_list)

    N_train = signal.shape[1]
    for i in range(N_train):
        psi,Aj = calculate_wavelet(eigenval,eigenvec,J, eps)
        Wf = weighted_wavelet_transform(psi,signal[:,i], N)
        these_features = generate_feature(psi, Wf, Aj, signal[:,i], N, norm_list)
        feature.append(np.concatenate(these_features, axis=0))
    return feature

def compute_scattering_features(data, norm_list, J):
    eigenval = data.node_attr_eig.numpy()[None,:]
    eigenvec = data.eigvec.numpy()

    if data.x is None:
        signal = data.pos.numpy()
    else:
        signal = data.x.numpy()
    
    eps = data.eps
    N = signal.shape[0]
    feature = compute_all_features(eigenval, eigenvec, signal, eps, N, norm_list, J)
    return np.stack(feature) # number of signals x scattering feats dim



if __name__=='__main__':
    import torch_geometric.transforms as T
    from torch_geometric.transforms.knn_graph import KNNGraph
    from torch_geometric.datasets import ModelNet
    display_sample = 2048  #@param {type:"slider", min:256, max:4096, step:16}
    modelnet_dataset_alias = "ModelNet10" #@param ["ModelNet10", "ModelNet40"] {type:"raw"}
    k =5 

    def signal_transform(x):
        x.x = x.pos
        return x
    
    knn_transform = KNNGraph(k=5)
    pre_transform = T.Compose([T.NormalizeScale(), T.SamplePoints(display_sample), KNNGraph(k = k) ])
    transform = signal_transform # T.SamplePoints(2048)
    train_dataset = ModelNet(
        root= os.path.join(DATA_DIR,modelnet_dataset_alias),
        name=modelnet_dataset_alias[-2:],
        train=True,
        transform=transform,
        pre_transform=pre_transform
    )
    val_dataset = ModelNet(
        root=os.path.join(DATA_DIR,modelnet_dataset_alias),
        name=modelnet_dataset_alias[-2:],
        train=False,
        transform=transform,
        pre_transform=pre_transform
    )

    from torch_geometric.loader import DataLoader
    data_list = []
    for ix in range(4):
        data = train_dataset[ix]
        #data = lap_transform(data)
        data_list.append(data)
    loader = DataLoader(data_list, batch_size=3, shuffle=True)
    for i,b in enumerate(loader):
        break

    data = b[0]
    from pcnn.data.utils import laplacian_epsilon
    data_ = laplacian_epsilon(data,eps="auto",K = 5)
    norm_list = [1, 2, 3, 4]
    J = 8
    data_filtered = compute_scattering_features(data,norm_list = norm_list, J = J)