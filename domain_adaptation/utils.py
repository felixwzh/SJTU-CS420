import gzip
import cPickle as pkl
import numpy as np
import tensorflow as tf
import random

random.seed(27)
np.random.seed(27)

def group_id_2_label(group_ids, num_class):
    labels = np.zeros([len(group_ids), num_class])
    for i in range(len(group_ids)):
        labels[i, group_ids[i]] = 1
    return labels

def load_mnist():
    data_num_train = 60000  # The number of figures
    data_num_test = 10000  # test num
    fig_w = 45  # width of each figure
    xt = np.fromfile("./data/mnist_train/mnist_train_data", dtype=np.uint8)
    yt_ = np.fromfile("./data/mnist_train/mnist_train_label", dtype=np.uint8)
    xt_test = np.fromfile("./data/mnist_test/mnist_test_data", dtype=np.uint8)
    yt_test_ = np.fromfile("./data/mnist_test/mnist_test_label", dtype=np.uint8)
    xt=xt/255.
    xt_test=xt_test/255.
    xt=xt.reshape([60000,fig_w*fig_w])
    xt_test=xt_test.reshape([10000,fig_w*fig_w])
    yt = np.zeros([60000, 10])
    yt_test = np.zeros([10000, 10])
    for i in range(60000):
        yt[i][yt_[i]] = 1
    for i in range(10000):
        yt_test[i][yt_test_[i]] = 1
    return xt, yt, xt_test, yt_test

def load_s_usps(size=1):
    random.seed(1)
    data_dir = 'data/usps_28x28.pkl'
    xs_raw, ys, xs_test_raw, ys_test = load_usps(data_dir, one_hot=True, flatten=True)

    xs_raw = xs_raw.reshape(-1, 28, 28)
    xs_test_raw = xs_test_raw.reshape(-1, 28, 28)

    xs = np.zeros([xs_raw.shape[0], 45, 45])
    xs_test = np.zeros([xs_test_raw.shape[0], 45, 45])

    if size==1:
        for i in range(xs_raw.shape[0]):
            j = random.randint(0, 17)
            k = random.randint(0, 17)
            xs[i, j:j + 28, k:k + 28] = xs_raw[i]
    else:
        xs_list=[]
        ys_list=[]
        for time in range(size):
            xs = np.zeros([xs_raw.shape[0], 45, 45])
            for i in range(xs_raw.shape[0]):
                j = random.randint(0, 17)
                k = random.randint(0, 17)
                xs[i, j:j + 28, k:k + 28] = xs_raw[i]
            xs_list.append(xs.copy())
            ys_list.append(ys.copy())
        xs=np.concatenate(xs_list,0)
        ys=np.concatenate(ys_list,0)


    for i in range(xs_test_raw.shape[0]):
        j = random.randint(0, 17)
        k = random.randint(0, 17)
        xs_test[i, j:j + 28, k:k + 28] = xs_test_raw[i]

    xs = xs.reshape(-1, 45 * 45)
    xs_test = xs_test.reshape(-1, 45 * 45)

    return xs, ys, xs_test, ys_test

def load_usps(data_dir, one_hot=True, flatten=True):
    usps = pkl.load(gzip.open(data_dir, "rb"))
    # 7438, 1, 28, 28
    train_images = usps[0][0]
    # 7438x[0~9]
    train_labels = usps[0][1]
    # 1860
    test_images = usps[1][0]
    test_labels = usps[1][1]
    if flatten:
        train_images = train_images.reshape(train_images.shape[0], -1)
        test_images = test_images.reshape(test_images.shape[0], -1)
    if one_hot:
        train_labels = group_id_2_label(train_labels, 10)
        test_labels = group_id_2_label(test_labels, 10)
    return train_images, train_labels, test_images, test_labels


def weight_variable(shape, name):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial, name=name)


def bias_variable(shape, name):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial, name=name)


def conv2d(x, w):
    return tf.nn.conv2d(x, w, strides=[1, 1, 1, 1], padding="SAME")


def max_pool_2x2(x):
    return tf.nn.max_pool(x, ksize=[1, 2, 2, 1],
                          strides=[1, 2, 2, 1], padding="SAME")


def shuffle_aligned_list(data):
    num = data[0].shape[0]
    shuffle_index = np.random.permutation(num)
    return [d[shuffle_index] for d in data]


def batch_generator(data, batch_size, shuffle=True):
    if shuffle:
        data = shuffle_aligned_list(data)
    batch_count = 0
    while True:
        if batch_count * batch_size + batch_size >= data[0].shape[0]:
            batch_count = 0
            if shuffle:
                data = shuffle_aligned_list(data)
        start = batch_count * batch_size
        end = start + batch_size
        batch_count += 1
        yield [d[start:end] for d in data]


def compute_pairwise_distances(x, y):
    if not len(x.get_shape()) == len(y.get_shape()) == 2:
        raise ValueError('Both inputs should be matrices.')
    if x.get_shape().as_list()[1] != y.get_shape().as_list()[1]:
        raise ValueError('The number of features should be the same.')

    norm = lambda x: tf.reduce_sum(tf.square(x), 1)
    return tf.transpose(norm(tf.expand_dims(x, 2) - tf.transpose(y)))


def gaussian_kernel_matrix(x, y, sigmas):
    beta = 1. / (2. * (tf.expand_dims(sigmas, 1)))
    dist = compute_pairwise_distances(x, y)
    s = tf.matmul(beta, tf.reshape(dist, (1, -1)))
    return tf.reshape(tf.reduce_sum(tf.exp(-s), 0), tf.shape(dist))


def maximum_mean_discrepancy(x, y, kernel=gaussian_kernel_matrix):
    cost = tf.reduce_mean(kernel(x, x))
    cost += tf.reduce_mean(kernel(y, y))
    cost -= 2 * tf.reduce_mean(kernel(x, y))
    cost = tf.where(cost > 0, cost, 0, name='value')
    return cost


def fc_layer(input_tensor, input_dim, output_dim, layer_name, act=tf.nn.relu, input_type='dense'):
    with tf.name_scope(layer_name):
        weight = tf.Variable(tf.truncated_normal([input_dim, output_dim], stddev=1. / tf.sqrt(input_dim / 2.)), name='weight')
        bias = tf.Variable(tf.constant(0.1, shape=[output_dim]), name='bias')
        if input_type == 'sparse':
            activations = act(tf.sparse_tensor_dense_matmul(input_tensor, weight) + bias)
        else:
            activations = act(tf.matmul(input_tensor, weight) + bias)
        return activations
