import tensorflow as tf
import pandas as pd
import numpy as np
import shutil,os


from sklearn.metrics import roc_auc_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.decomposition import PCA


def read_train_make_split(X_npy,dev_split):

    # Assumes last column
    y = X_npy[:,X_npy.shape[1] - 1]
    X_train, X_dev, y_train,y_dev = train_test_split(X_npy,y,test_size=dev_split,stratify=y)

    return X_train, X_dev, y_train,y_dev

def build_optimiser_cost(logits,sigmoids,num_labels,fc1_weights,fc2_weights, fc3_weights, wt):

    pos_wt = 0.1  #  < 0 to reduce false positives, which may be what want in unbalanced data
    lambd = 0.01

    with tf.name_scope('cross_entropy'):

        # This is the labels tagged to the dataset
        ground_truth_input = tf.placeholder(tf.float32,shape = [None], name='groundtruth_input')
        learning_rate_input = tf.placeholder(tf.float32, [], name='learning_rate_input')

        # Binary cross-entropy loss
        weighted_cross_entropy_mean = tf.nn.weighted_cross_entropy_with_logits(targets=ground_truth_input, logits=logits,pos_weight=pos_wt,name="loss_binary_xe")
        loss = tf.reduce_mean(weighted_cross_entropy_mean ,name="cross_entropy_loss") # + lambd * tf.nn.l2_loss(fc1_weights)  + lambd * tf.nn.l2_loss(wt)  #lambd * tf.nn.l2_loss(fc2_weights) + lambd * tf.nn.l2_loss(fc3_weights)

        #train_step = tf.train.AdadeltaOptimizer(learning_rate=learning_rate_input).minimize(loss)
        train_step = tf.train.AdamOptimizer(learning_rate=learning_rate_input).minimize(loss)
        #train_step = tf.train.GradientDescentOptimizer(learning_rate = learning_rate_input).minimize(loss)

        # Construct the confusion matrix
        threshold = tf.constant(0.5,dtype=tf.float32,name="threshold")
        #auc = tf.metrics.auc(tf.convert_to_tensor(ground_truth_input, dtype=tf.float32), sigmoids, summation_method='minoring')

        predictions = tf.cast(tf.math.greater(sigmoids,threshold),dtype=tf.float32)
        correct_prediction = tf.equal(predictions, ground_truth_input, name='correct_prediction')
        confusion_matrix = tf.confusion_matrix(
            ground_truth_input, predictions, num_classes= num_labels, name = "confusion_matrix")
        #evaluation_step = tf.reduce_mean(tf.cast(correct_prediction, tf.float32), name="eval_step")


        return ground_truth_input, learning_rate_input, train_step, weighted_cross_entropy_mean, loss, confusion_matrix



def build_graph(fc1_units, fc2_units,fc3_units):

    with (tf.variable_scope("input_layer")):

        inputs = tf.placeholder(shape=[None,64],name="input_train",dtype=tf.float32)
        dropout_1 = tf.placeholder(name="dropout_1",dtype=tf.float32)
        dropout_2 = tf.placeholder( name="dropout_2", dtype=tf.float32)
        dropout_3 = tf.placeholder( name="dropout_3", dtype=tf.float32)

    with (tf.variable_scope("fc_layers")):

        he_init_fc_1 = tf.contrib.layers.variance_scaling_initializer()
        he_init_fc_2 = tf.contrib.layers.variance_scaling_initializer()
        he_init_fc_3 = tf.contrib.layers.variance_scaling_initializer()


        fc1 = tf.layers.dense(inputs,fc1_units,activation=tf.nn.relu,name="layer_fc1",kernel_initializer=he_init_fc_1)
        fc1_weights = tf.get_default_graph().get_tensor_by_name(os.path.split(fc1.name)[0] + '/kernel:0')
        fc1_drop = tf.nn.dropout(fc1,dropout_1)

        fc2 = tf.layers.dense(fc1_drop, fc2_units, activation=tf.nn.relu, name="layer_fc2",kernel_initializer=he_init_fc_2)
        fc2_weights = tf.get_default_graph().get_tensor_by_name(os.path.split(fc2.name)[0] + '/kernel:0')
        #fc2_weights = None
        fc2_drop = tf.nn.dropout(fc2, dropout_2)

        fc3 = tf.layers.dense(fc2_drop, fc3_units, activation=tf.nn.relu, name="layer_fc3",kernel_initializer=he_init_fc_3)
        fc3_weights = tf.get_default_graph().get_tensor_by_name(os.path.split(fc3.name)[0] + '/kernel:0')
        #fc3_weights = None
        fc3_drop = tf.nn.dropout(fc3, dropout_3)

    with (tf.variable_scope("sigmoid_layer")):

        xavier_init_fc_4 = tf.contrib.layers.xavier_initializer()
        wt = tf.get_variable(name="lreg_wt",shape=[fc3_units,1],initializer=xavier_init_fc_4)
        bias = tf.get_variable(name="lreg_bias",shape=[1],initializer=tf.zeros_initializer())

        logits = tf.add(tf.matmul(fc3_drop,wt),bias)
        logits_sq = tf.squeeze(logits,axis=1,name="logits") # to match the ground truth labels shape

        sig = tf.nn.sigmoid(logits_sq)


    return inputs, logits_sq, sig, dropout_1,dropout_2,dropout_3, fc1_weights,fc2_weights, fc3_weights, wt



def get_mini_batch(X_train_0,X_train_1,mini_batch_size, train_indx_0, train_indx_1):

    # Mini batch size should be even
    if mini_batch_size % 2 != 0:
        mini_batch_size += 1

    #sample_0 = X_train_0.sample(n = int(round(mini_batch_size * 0.99987259)))
    #sample_1 = X_train_1.sample(n= int(round(mini_batch_size * 0.012741)))

    sample_train_indexes_0 = np.random.choice(train_indx_0,mini_batch_size * 1,replace=False)
    sample_train_indexes_1 = np.random.choice(train_indx_1, mini_batch_size * 1, replace=False)

    #sample_0 = X_train_0.sample(n = int(round((mini_batch_size * 1))))
    #sample_1 = X_train_1.sample(n = int(round(mini_batch_size)))

    sample_0 = X_train_0[sample_train_indexes_0]
    sample_1 = X_train_1[sample_train_indexes_1]

    mini_batch = np.vstack((sample_0,sample_1))
    np.random.shuffle(mini_batch)
    #mini_batch_sample = pd.concat([sample_0,sample_1],ignore_index=True)
    #mini_batch = mini_batch_sample.sample(frac=1).reset_index(drop=True) # reshuffles

    return mini_batch


def train_model(X_train,X_dev,y_train,y_dev, chkpoint_dir):

    fc1_units = 256
    fc2_units = 64
    fc3_units = 64

    drop_1 = 1.0
    drop_2 = 0.6
    drop_3 = 0.6

    num_epochs = 200000
    num_labels = 2

    learning_rate = 0.0001

    mini_batch_size = 512


    train_tensorboard_dir = '/home/nitin/Desktop/google_analytics/google_analytics_revenue/train_tensorboard/'
    valid_tensorboard_dir = '/home/nitin/Desktop/google_analytics/google_analytics_revenue/valid_tensorboard/'



    with tf.Graph().as_default() as gr:

        inputs, logits, sig , dropout_1,dropout_2,dropout_3, fc1_weights,fc2_weights, fc3_weights, wt = build_graph(fc1_units,fc2_units,fc3_units)

        ground_truth_input, learning_rate_input, train_step,  weighted_cross_entropy_mean, loss, confusion_matrix = \
        build_optimiser_cost(logits,sig,num_labels, fc1_weights,fc2_weights, fc3_weights, wt)

    with tf.Session(graph=gr) as sess:

        saver = tf.train.Saver()
        sess.run(tf.global_variables_initializer())
        sess.run(tf.local_variables_initializer())

        #X_train_0 = X_train.loc[X_train['is_revenue'] == 0]
        #X_train_1 = X_train.loc[X_train['is_revenue'] != 0]

        X_train_0 = X_train[X_train[:,X_train.shape[1] - 1] == 0]
        X_train_1 = X_train[X_train[:, X_train.shape[1] - 1] != 0]

        train_idxs_0 = np.arange(0, X_train_0.shape[0], 1)
        train_idxs_1 = np.arange(0, X_train_1.shape[0], 1)

        print(train_idxs_0.shape)
        print(train_idxs_1.shape)

        # Tensorboard init
        if (os.path.exists(train_tensorboard_dir)):
            shutil.rmtree(train_tensorboard_dir)
        os.mkdir(train_tensorboard_dir)
        if (os.path.exists(valid_tensorboard_dir)):
            shutil.rmtree(valid_tensorboard_dir)
        os.mkdir(valid_tensorboard_dir)
        if (os.path.exists(chkpoint_dir)):
            shutil.rmtree(chkpoint_dir)

        os.mkdir(chkpoint_dir)


        train_writer = tf.summary.FileWriter(train_tensorboard_dir, sess.graph)
        valid_writer = tf.summary.FileWriter(valid_tensorboard_dir)

        xent_counter = 0
        val_batch = 1

        #X_dev.drop('is_revenue', axis=1, inplace=True)
        X_dev = X_dev[:,:-1]
        print (X_dev.shape)

        #X_dev_npy = X_dev.as_matrix()
        #nans_index = np.isnan(X_dev_npy)
        #X_dev_npy[nans_index] = 0

        #y_dev_npy = y_dev.as_matrix()

        print('Sum is:' + str(y_dev.sum()))

        for i in range(1,num_epochs + 1):

            #if (i >= 800 and learning_rate != 0.0001):
            #    learning_rate = 0.0001

            # Get mini batch for the epoch
            mini_batch = get_mini_batch(X_train_0=X_train_0, X_train_1=X_train_1, mini_batch_size=mini_batch_size,train_indx_0=train_idxs_0,train_indx_1=train_idxs_1)
            mini_batch_y = mini_batch[:,mini_batch.shape[1] - 1]
            mini_batch = mini_batch[:,:-1]
            print (mini_batch_y.sum())
            print (mini_batch_y.shape)

            #mini_batch_npy = mini_batch.as_matrix()
            #mini_batch_npy_y = mini_batch_y.as_matrix()
            #nans_index = np.isnan(mini_batch_npy)
            #mini_batch_npy[nans_index] = 0

            print ('Mini-batch retrieved.')
            # Put inputs through the graph
            _, l, total_conf_matrix,  wt_mean = sess.run(
                [
                    train_step, loss, confusion_matrix, weighted_cross_entropy_mean

                ],
                feed_dict={
                    inputs: mini_batch,
                    ground_truth_input: mini_batch_y,
                    learning_rate_input: learning_rate,
                    dropout_1 : drop_1,
                    dropout_2 : drop_2,
                    dropout_3:  drop_3

                })

            # Write loss to tensorflow for each batch
            xent_train_summary = tf.Summary(
                value=[tf.Summary.Value(tag="cross_entropy_avg", simple_value=l)])
            xent_counter += 1
            train_writer.add_summary(xent_train_summary, xent_counter)

            print ('The training loss after batch ' + str(i) + ' is:' + str(l))

            print('Training Confusion Matrix: ' + '\n' + str(total_conf_matrix))
            true_pos = np.sum(np.diag(total_conf_matrix))
            all_pos = np.sum(total_conf_matrix)
            print('Training data points:' + str(all_pos))

            if (i % 10 == 0):
                print('Saving checkpoint for epoch:' + str(i))
                saver.save(sess=sess, save_path=chkpoint_dir + 'google_analytics_revenue_model.ckpt',
                           global_step=i)

            if (i % val_batch == 0): # dev metrics after 10 epochs

                sg, val_l , valid_conf_matrix = sess.run(
                        [sig, loss, confusion_matrix],
                    feed_dict={
                        inputs: X_dev,
                        ground_truth_input: y_dev,
                        dropout_1 : 1.0,
                        dropout_2 : 1.0,
                        dropout_3 : 1.0
                    })

                auc = roc_auc_score(y_dev,sg,average="weighted")

                print('Validation Confusion Matrix: ' + '\n' + str(valid_conf_matrix))
                true_pos = np.sum(np.diag(valid_conf_matrix))
                all_pos = np.sum(valid_conf_matrix)
                print('Validation data points:' + str(all_pos))

                print('Validation AUC on batch ' + str(i / val_batch) + ' is:' + str(auc))
                print('Validation loss ' + str(i / val_batch) + ' is:' + str(val_l))

                auc_valid_summary = tf.Summary(value=[tf.Summary.Value(tag="auc_valid_summary", simple_value=auc)])
                valid_writer.add_summary(auc_valid_summary, i / val_batch)

                loss_valid_summary = tf.Summary(value=[tf.Summary.Value(tag="loss_valid_summary", simple_value=val_l)])
                valid_writer.add_summary(loss_valid_summary, i / val_batch)


def sigmoid(x):
    return 1/(1 + np.exp(-x))



def test_inference(X_test,threshold,chkpoint_dir,chkpoint_file,write_file):


    X_fullvisitorid = X_test.loc[:,'fullVisitorId']
    X_fullvisitorid_npy = X_fullvisitorid.as_matrix()

    X_test.drop('Unnamed: 0', axis=1, inplace=True)
    X_test.drop('fullVisitorId', axis=1, inplace = True)
    X_test.drop('is_revenue', axis=1,inplace = True)

    X_test_logits = inference_logits(X_test,chkpoint_dir,chkpoint_file)
    X_test_sigmoid = sigmoid(X_test_logits)
    X_test_pred = int((X_test_sigmoid > threshold))

    X_test_final = np.vstack((X_fullvisitorid_npy,X_test_pred)).T
    X_test_final_df = pd.DataFrame(X_test_final)

    X_test_final_df.to_csv(write_file)


def perform_pca(X_df_train, X_df_test = None):

    """

    :param X_df_train:
    :param X_df_test:
    :return: The train and test numpy arrays with PCA transform
    """

    y = X_df_train.loc[:, 'is_revenue']
    #y_test = X_df_test.loc[:, 'is_revenue']
    #y_npy_test = y_test.as_matrix()

    # Drop befre PCA - train only
    X_df_train.drop('is_revenue', axis=1, inplace=True)

    # captures 86.52% of variance
    pca = PCA(n_components = 64)
    fit = pca.fit(X_df_train)

    #print ('The PCA training fit')
    #print(np.sum(pca.explained_variance_ratio_))
    #print(pca.explained_variance_ratio_)

    X_pca_train = pca.transform(X_df_train)
    y_npy = y.as_matrix()
    X_pca_train = np.c_[X_pca_train,y_npy]
    #X_pca_test = pca.transform(X_df_npy_test)
    #print (X_pca_test.shape)

    return X_pca_train




def pick_threshold(X_train_full, y_train_full,chkpoint_dir,chkpoint_file):

    """
    :param X_train_full: Full X_matrix of training data. Includes the label column.
    :param y_train_full: Full y_matrix of training labels.
    :param chkpoint_dir: Directory where checkpoints are stored
    :param chkpoint_file: the model checkpoint file
    :return: The threshold that gives the best youden's J statistic, for the entire train set.
    """

    # Picks a threshold using the best Youden's J statistic for the threshold
    # At this point, the best model has already been picked by AUC
    X_train_full.drop('is_revenue', axis=1, inplace=True)

    X_logits_np = inference_logits(X_train_full,chkpoint_dir,chkpoint_file)

    x_sigmoid = sigmoid(X_logits_np)
    y_full_npy = y_train_full.as_matrix()

    # Loop through the thresholds to get the best Youden's J
    youden_j_dict = {}
    threshold = 0

    while (threshold <= 1):
        y_hat = (x_sigmoid > threshold)
        conf_matrix = confusion_matrix(y_full_npy,y_hat)

        print ('Threshold:' + str(threshold))
        print (conf_matrix)

        sensitivity = conf_matrix[1,1] / (conf_matrix[1,1] + conf_matrix[1,0])
        specificity = conf_matrix[0,0] / (conf_matrix[0,0] + conf_matrix[0,1])
        youden_j = sensitivity + specificity - 1

        youden_j_dict[str(threshold)] = youden_j

        threshold += 0.05

    return float(max(youden_j_dict,key=youden_j_dict.get))



def inference_logits(X_mat, chkpoint_dir, chkpoint_file):

    """
    :param X_mat: Matrix to make predictions for. Must not include the is_revenue column
    :param chkpoint_dir: directory with checkpoint files
    :param chkpoint_file: the checkpoint file to use
    :return: a numpy array with the logits for the X_mat
    """

    fc1_units = 512
    fc2_units = 512
    fc3_units = 512

    chkpoint_model_file = chkpoint_dir + chkpoint_file
    num_labels = 2

    n_rows = X_mat.shape[0]
    batch_size = 1024

    i_lower = 0

    logits_full = []

    with tf.Graph().as_default() as gr:
        inputs, logits, _, dropout_1, dropout_2, dropout_3, _, _, _, _ = build_graph(fc1_units, fc2_units, fc3_units)


    with tf.Session(graph=gr) as sess:

        saver = tf.train.Saver()
        saver.restore(sess, chkpoint_model_file)

        if (i_lower + batch_size > n_rows):
            batch_size = n_rows - i_lower
        else:
            batch_size = 1024

        # Inference on all rows
        while (i_lower < n_rows):

            # Subset the data
            X_subset = X_mat[i_lower:i_lower + batch_size]

            # Fill in NA
            X_subset_npy = X_subset.as_matrix()
            nans_index = np.isnan(X_subset_npy)
            X_subset_npy[nans_index] = 0

            predictions = sess.run(logits,
                                   feed_dict={
                                       inputs : X_subset_npy,
                                       dropout_1 : 1.0,
                                       dropout_2 : 1.0,
                                       dropout_3 : 1.0
                                   })

            logits_full.extend(predictions.tolist())
            i_lower = i_lower + batch_size


        logits_np = np.asarray(logits_full)

        return logits_np


def main():

    file_name = '/home/nitin/Desktop/google_analytics/google_analytics_revenue/dfgoog_mod1_v2.csv'
    test_file_name = '/home/nitin/Desktop/google_analytics/google_analytics_revenue/dfgoog_test_mod1_v2.csv'

    chkpoint_dir = '/home/nitin/Desktop/google_analytics/google_analytics_revenue/chkpoint_dir/'
    chkpoint_file = 'google_analytics_revenue_model.ckpt-20000'

    inference_file = '/home/nitin/Desktop/google_analytics/google_analytics_revenue/test_mod1_inf.csv'
    pca_file = '/home/nitin/Desktop/google_analytics/google_analytics_revenue/pca_train.csv'

    dev_split = 0.1


    # Read train file, drop columns, do some PCA
    data_frame = pd.read_csv(file_name, low_memory=False)
    data_frame.drop('Unnamed: 0', axis=1, inplace=True)

    # This will return a numpy array with label as the last column
    X_pca = perform_pca(data_frame)
    print (X_pca.shape)
    #mat = np.matrix(X_pca)

    #with open(pca_file,'w') as f:
    #    for line in mat:
    #        #print (line)
    #        np.savetxt(f, line)

    # do train - dev split on numpy array
    X_train,X_dev,y_train,y_dev = read_train_make_split(X_pca,dev_split)
    #X_test = pd.read_csv(test_file_name, low_memory=False)


    # Trains the model using AUC
    train_model(X_train,X_dev,y_train,y_dev,chkpoint_dir)
    X_full = X_train.append(X_dev,ignore_index = True)
    y_full = y_train.append(y_dev)
    thres = pick_threshold(X_full,y_full,chkpoint_dir,chkpoint_file)

    print('Selected threshold is:' + str(thres))


    #test_inference(X_test,thres,chkpoint_dir,chkpoint_file,inference_file)




main()