import utils as ut
import numpy as np

from mnist import MNIST

# MNIST Constants
mndata = MNIST('./MNIST')
test_imgs, test_lbls = mndata.load_testing()
train_imgs, train_lbls = mndata.load_training()

train_imgs = np.asarray(train_imgs)
train_lbls = np.asarray(train_lbls)

test_imgs = np.asarray(test_imgs)
test_lbls = np.asarray(test_lbls)


class Network(object):
    def __init__(self, data, label, n_in, hidden_layer_sizes, n_out, rng=None, dropout=True):

        self.x = data / np.max(data)
        self.y = label
        self.dropout = dropout

        self.hidden_layers = []
        self.dropout_masks = []
        self.n_layers = len(hidden_layer_sizes)

        if rng is None:
            rng = np.random.RandomState(1234)

        assert self.n_layers >= 0

        # construct multi-layer
        for i in range(self.n_layers):

            # layer_size
            if i == 0:
                data_size = n_in
            else:
                data_size = hidden_layer_sizes[i - 1]

            # layer_data
            if i == 0:
                layer_data = self.x

            else:
                layer_data = self.hidden_layers[-1].output

            # construct hidden_layer
            hidden_layer = HiddenLayer(data=layer_data,
                                       n_in=data_size,
                                       n_out=hidden_layer_sizes[i],
                                       rng=rng)

            self.hidden_layers.append(hidden_layer)

        if self.n_layers != 0:
            self.log_layer = LogisticRegression(data=self.hidden_layers[-1].output,
                                                label=self.y,
                                                n_in=hidden_layer_sizes[-1],
                                                n_out=n_out)
        else:
            self.log_layer = LogisticRegression(data=self.x,
                                                label=self.y,
                                                n_in=n_in,
                                                n_out=n_out)

    def train(self, batch=True):
        data = np.asarray([(x, y) for x, y in zip(self.x, self.y)])
        np.random.shuffle(data)

        if batch and ut.BATCH_SIZE <= len(self.x):
            batch_size_range = int(len(self.x) / ut.BATCH_SIZE) - 1
        else:
            batch_size_range = 1
        for i in range(batch_size_range):
            print("------------------ Batch #" + str(i + 1) + " of " + str(batch_size_range))

            dropout = i == 0

            cost = self.feed_forward_batch(
                data=np.asarray([x for (x, y) in data[(i * ut.BATCH_SIZE):((i + 1) * ut.BATCH_SIZE)]]),
                labels=np.asarray([y for (x, y) in data[(i * ut.BATCH_SIZE):((i + 1) * ut.BATCH_SIZE)]]),
                dropout=dropout)

            self.back_prop_batch()
            self.update_batch()

            print('Cost: ' + str(cost))

    def feed_forward_batch(self, data=None, labels=None, rng=None, dropout=False):
        self.dropout_masks = []

        if labels is None:
            labels = self.y

        if data is not None:
            layer_data = data
        else:
            layer_data = self.x

        for i in range(self.n_layers):
            layer_data = self.hidden_layers[i].feed_forward(data=layer_data)

            if self.dropout:
                mask = self.hidden_layers[i].dropout(data=layer_data, p=ut.DROPOUT_PERCENTAGE, rng=rng)
                layer_data *= mask

                self.dropout_masks.append(mask)

        return self.log_layer.feed_forward_layer(data=layer_data, labels=labels)

    def back_prop_batch(self):
        self.log_layer.back_prop_layer()

        for i in reversed(range(self.n_layers)):
            if i == self.n_layers - 1:
                prev_layer = self.log_layer
            else:
                prev_layer = self.hidden_layers[i + 1]

            self.hidden_layers[i].back_prop(prev_layer=prev_layer)

            if self.dropout:
                self.hidden_layers[i].prime_output *= self.dropout_masks[i]  # also mask here

    def update_batch(self):
        for i in range(self.n_layers):
            self.hidden_layers[i].update()

        self.log_layer.update()

    def predict(self, x):
        layer_data = x

        for i in range(self.n_layers):
            if self.dropout:
                self.hidden_layers[i].W = ut.DROPOUT_PERCENTAGE * self.hidden_layers[i].W
                self.hidden_layers[i].b = ut.DROPOUT_PERCENTAGE * self.hidden_layers[i].b

            layer_data = self.hidden_layers[i].feed_forward(data=layer_data)

        return self.log_layer.predict(layer_data)

    def test(self, data, labels):
        self.feed_forward_batch(data=data, labels=labels)

        results = [(np.argmax(x), y) for x, y in zip(self.log_layer.output, labels)]

        return sum(int(x == y) for (x, y) in results) / labels.size


'''
Hidden Layer
'''


class HiddenLayer(object):
    def __init__(self, data, n_in, n_out, W=None, b=None, rng=None, activation=ut.sigmoid):

        if rng is None:
            rng = np.random.RandomState(1234)

        if W is None:
            W = np.random.normal(ut.MU, ut.SIGMA, (n_in, n_out))

        if b is None:
            b = np.random.normal(ut.MU, ut.SIGMA, n_out)

        self.rng = rng
        self.x = data

        self.W = W
        self.b = b

        self.output = np.zeros(n_out)
        self.prime_output = np.zeros((n_out, n_in))

        if activation == ut.tanh:
            self.prime_activation = ut.tanh_prime

        elif activation == ut.sigmoid:
            self.prime_activation = ut.sigmoid_prime

        elif activation == ut.ReLU:
            self.prime_activation = ut.ReLU_prime

        else:
            raise ValueError('activation function not supported.')

        self.activation = activation

    def feed_forward(self, data=None):
        if data is not None:
            self.x = data

        self.output = self.activation(np.dot(self.x, self.W) + self.b)
        return self.output

    def back_prop(self, prev_layer, data=None):
        if data is not None:
            self.x = data

        self.prime_output = self.prime_activation(prev_layer.x) * np.dot(prev_layer.prime_output, prev_layer.W.T)

    def update(self):
        self.W += ut.LEARNING_RATE * np.dot(self.x.T, self.prime_output)
        self.b += ut.LEARNING_RATE * np.mean(self.prime_output, axis=0)

    def dropout(self, data, p, rng=None):
        if rng is None:
            rng = np.random.RandomState(123)

        mask = rng.binomial(size=data.shape,
                            n=1,
                            p=1 - p)  # p is the prob of dropping

        return mask

    def set_wb(self, w, b):
        self.W = w
        self.b = b


'''
Logistic Regression
'''


class LogisticRegression(object):
    def __init__(self, data, label, n_in, n_out, activation_function=ut.sigmoid):
        self.x = data
        self.y = label
        self.W = np.random.normal(ut.MU, ut.SIGMA, (n_in, n_out))
        self.b = np.random.normal(ut.MU, ut.SIGMA, n_out)
        self.output = np.zeros(n_out)
        self.prime_output = np.zeros((n_out, n_in))
        self.activation_function = activation_function

    def feed_forward_layer(self, data=None, labels=None):
        if data is not None:
            self.x = data
        if labels is not None:
            self.y = labels

        self.output = self.activation_function(np.dot(self.x, self.W) + self.b)

        return self.cost()

    def back_prop_layer(self):
        self.prime_output = ut.cross_entropy_prime(self.output, self.y)

    def update(self):
        self.W += ut.LEARNING_RATE * np.dot(self.x.T, self.prime_output)
        self.b += ut.LEARNING_RATE * np.mean(self.prime_output, axis=0)

    def cost(self):
        return ut.cross_entropy(self.output, self.y)

    def predict(self, x):
        return self.activation_function(np.dot(x, self.W) + self.b)

    def set_wb(self, w, b):
        self.W = w
        self.b = b


def test_dropout():
    for i in range(ut.EPOCHS):
        # XOR
        x = np.array([[0, 0],
                      [0, 1],
                      [1, 0],
                      [1, 1]])

        y = np.array([0, 1, 1, 0])

        rng = np.random.RandomState(123)

        # construct Dropout MLP
        classifier = Network(data=x, label=y,
                             n_in=2, hidden_layer_sizes=[10, 10], n_out=2,
                             rng=rng)

        # train
        classifier.train()

        print('Accuracy: ' + str(classifier.test(x, y)))


if __name__ == "__main__":
    test_dropout()
