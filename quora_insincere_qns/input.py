import nltk
nltk.download('stopwords')
from nltk.corpus import stopwords
stop_words = set(stopwords.words('english'))

import pandas as pd
import re, os, shutil
import numpy as np
np.set_printoptions(threshold=np.nan)
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score

import tensorflow as tf

cutoff_shape = 2196017
glove_dim = 300
max_seq_len = 122
cutoff_seq = 70
max_sent_seq_len = 12 # 12 sentences in a doc

reload_mmap = False


'''
def load_npy_file(npy_file):

    mmap = np.memmap(npy_file, dtype='float32', mode='r', shape=(cutoff_shape + 2, glove_dim))

    print (mmap[[0,2196015,2196017,2196018]].shape)


def get_max_len(train_file):

    max = -1
    df = pd.read_csv(train_file,low_memory=False)
    for index, item in df.iterrows():
        l = len(str(item[1]).split(' '))
        #print (l)
        if (max < l):
            max = l

    print ('Max is:')
    print (max)
'''


def load_glove_vectors(memmap_loc, glove_file, reload_mmap = False):

    """
    Create a memmap
    """

    #wts = []
    glove_dict = {}

    i = 0

    mmap = None

    if (reload_mmap):
        mmap = np.memmap(memmap_loc, dtype='float32', mode='w+', shape=(cutoff_shape + 2, glove_dim))

    with open (glove_file,'r') as f:

        for index, line in enumerate(f):
            l = line.split(' ')

            #add to the dictionary
            glove_dict[str(l[0]).strip().lower()] = index

            # Add to memmap
            if (reload_mmap):
                del l[0]
                mmap[index,:] = l

            #wts.append(l)
            i += 1
            #if (i > cutoff_shape): # for dev purposes only
            #    break


    # contains the word embeddings. assumes indexes start from 0-based in the txt file

    if (reload_mmap):
        # Add the UNK
        unk_wt = np.random.randn(glove_dim)
        #wts.append(unk_wt.tolist())
        mmap[i:] = unk_wt
        i += 1

        # Add the _NULL
        null_wt = np.zeros(glove_dim)
        #wts.append(null_wt.tolist())
        mmap[i:] = null_wt
        mmap.flush()

    #weights = np.asarray(wts)

    #assert weights.shape[1] == glove_dim
    #assert weights.shape[0] == cutoff_shape + 3

    return glove_dict


def get_train_df_glove_dict(train_file, glove_file,mmap_loc):


    df = pd.read_csv(train_file,low_memory=False)
    y = df.loc[:,'target']

    X_train, X_dev, y_train, y_dev = train_test_split(df, y, test_size=0.01, stratify=y, random_state = 42)

    # creates the mmap
    glove_dict = load_glove_vectors(mmap_loc,glove_file,reload_mmap)

    X_train_0 = X_train.loc[X_train['target'] == 0]
    X_train_1 = X_train.loc[X_train['target'] == 1]

    X_train_0_sample = X_train_0.sample(n=500)
    X_train_1_sample = X_train_1.sample(n=50)

    X_dev_0 = X_dev.loc[X_dev['target'] == 0]
    X_dev_1 = X_dev.loc[X_dev['target'] == 1]

    X_dev_0_sample = X_dev_0.sample(n=100)
    X_dev_1_sample = X_dev_1.sample(n=20)

    X_train_f = pd.concat([X_train_0_sample,X_train_1_sample],axis=0)
    X_dev_f = pd.concat([X_dev_0_sample, X_dev_1_sample], axis=0)

    #return X_train, X_dev, glove_dict

    return X_train_f, X_dev_f, glove_dict



def process_questions(qn_df, glove_dict, mmap):

    #UNK = 2196017
    UNK = cutoff_shape
    _NULL = cutoff_shape + 1
    sentence_batch_len = []
    sentence_batch_len_2 = []

    #glove_dict, _ = load_glove_vectors(glove_file)
    #train_df = pd.read_csv(train_file, low_memory=False)
    #test_df = pd.read_csv(test_file, low_memory=False)
    #train_qns = train_df.iloc[:,1]


    qn_ls_word_idx = []
    qn_batch_len = []
    #max_sentence_len = -1

    l = 0
    for index, item in qn_df.iterrows():

        #if (index > 1000): # dev purposes only
        #    break

        qn1 = item[1].split('. ') # Extract the sentences
        #print (qn1)
        qn2 = [x.split('? ') for x in qn1]
        #print (qn2)
        qn3 = [x for y in qn2 for x in y if x != '']
        #print (qn3)
        qn_ls = [re.sub('[^A-Za-z0-9 ]+', '', q) for q in qn3]
        qn_ls = [x.lower() for x in qn_ls if x not in stop_words]

        sentence_batch_len.append(len(qn_ls))


        # word level tokens
        qn_ls_word = [x.split(' ') for x in qn_ls]
        #print (qn_ls_word)

        # Bit misnomer. qn_ls_word is still array of sentences in each document / answer

        for y in qn_ls_word:

            tmp = [glove_dict[x] if (x in glove_dict.keys()) else UNK for x in y]
            #word_batch_len = len(tmp)
            #tmp += [_NULL] * (max_seq_len - len(tmp)) # pad to the max_seq_len

            #if (len(tmp) > max_sentence_len):
            #    max_sentence_len = len(tmp)

            # Word embedding lookup from memmapped file
            #tmp_npy = mmap[tmp]
            #tmp_npy = np.expand_dims(tmp_npy,axis=0)
            qn_ls_word_idx.append(tmp)



            qn_batch_len.append(len(tmp))
            sentence_batch_len_2.append(len(qn_ls))

    # Now we have max_len, a flattened sentence matrix, and batch sequence length for dynamic rnn.
    # Apply the _null padding.

    batch_shape = len(qn_ls_word_idx)
    #qn_ls_word_embd = np.empty((batch_shape, max_seq_len, glove_dim))
    qn_ls_word_embd = np.empty((batch_shape, cutoff_seq, glove_dim))

    for item in qn_ls_word_idx:
        item += [_NULL] * (max_seq_len - len(item))

        # Apply a cutoff
        item = item[:cutoff_seq]

        # Word embedding lookup from memmapped file
        tmp_npy = mmap[[item]]

        tmp_npy = np.expand_dims(tmp_npy,axis=0)

        qn_ls_word_embd[l] = tmp_npy

        l += 1


    #max_l = -1
    #for item in sentence_batch_len:
    #    if (max_l < item):
    #        max_l = item
    #print ('The max sentence batch')
    #print (max_l)

    #qn_npy = np.asarray(qn_ls_word_idx)


    return qn_ls_word_embd, qn_batch_len, sentence_batch_len, sentence_batch_len_2 # Flattened qn_lengths, and sentence_len at document level


def build_graph(max_sentence_len):

    def sparse_softmax(T):

        # Creating partition based on condition:
        condition_mask = tf.cast(tf.equal(T, 0.), tf.int32)
        partitioned_T = tf.dynamic_partition(T, condition_mask, 2)
        # Applying the operation to the target partition:
        partitioned_T[0] = tf.nn.softmax(partitioned_T[0],axis=0)

        # Stitching back together, flattening T and its indices to make things easier::
        condition_indices = tf.dynamic_partition(tf.range(tf.size(T)), tf.reshape(condition_mask, [-1]), 2)
        res_T = tf.dynamic_stitch(condition_indices, partitioned_T)
        res_T = tf.reshape(res_T, tf.shape(T))

        return res_T


    gru_units = 100
    output_size = 100

    gru_units_sent = 100
    output_size_sent = 100

    cell_fw = tf.nn.rnn_cell.LSTMCell(gru_units)
    cell_bw = tf.nn.rnn_cell.LSTMCell(gru_units)

    cell_sent_fw = tf.nn.rnn_cell.LSTMCell(gru_units_sent)
    cell_sent_bw = tf.nn.rnn_cell.LSTMCell(gru_units_sent)

    # First fetch the pre-trained word embeddings into variable
    # + 2 because of the UNK weight and the 0-index start
    #with tf.variable_scope("embedding_layer"):
        #embedding_const = tf.Variable(tf.constant(0.0,dtype=tf.float32,shape=[cutoff_shape + 3, glove_dim]),trainable=False,name="embedding_const")
        #embedding_placeholder = tf.placeholder(dtype=tf.float32,shape=[cutoff_shape + 3,glove_dim],name="embedding_placeholder")
        #embedding_init = embedding_const.assign(embedding_placeholder)

    # Now load the inputs and convert them to word vectors
    with tf.variable_scope("layer_inputs"):
        inputs = tf.placeholder(dtype=tf.float32, shape=[None,max_sentence_len,glove_dim],name="input")
        #inputs_embed = tf.nn.embedding_lookup(embedding_init,inputs,name="input_embed")
        batch_sequence_lengths = tf.placeholder(dtype=tf.int32,name="sequence_length")


    with tf.variable_scope("layer_word_hidden_states"):
        ((fw_outputs,bw_outputs),
         _) = (
            tf.nn.bidirectional_dynamic_rnn(cell_fw=cell_fw,
                                            cell_bw=cell_bw,
                                            inputs=inputs,
                                            sequence_length=batch_sequence_lengths,
                                            dtype=tf.float32,
                                            swap_memory=True,
                                            ))
    outputs_hidden = tf.concat((fw_outputs, bw_outputs), 2)

    with tf.variable_scope("layer_word_attention"):

        initializer = tf.contrib.layers.xavier_initializer()

        # Big brain #1
        attention_context_vector = tf.get_variable(name='attention_context_vector',
                                                   shape=[output_size * 2],
                                                   initializer=initializer,
                                                   dtype=tf.float32)

        input_projection = tf.contrib.layers.fully_connected(outputs_hidden, output_size * 2,
                                                  activation_fn=tf.nn.relu)
        vector_attn = tf.tensordot(input_projection,attention_context_vector,axes=[[2],[0]],name="vector_attn")
        attn_softmax = tf.map_fn(lambda batch:
                               sparse_softmax(batch)
                               , vector_attn, dtype=tf.float32)

        attn_softmax = tf.expand_dims(input=attn_softmax,axis=2,name='attn_softmax')

        weighted_projection = tf.multiply(outputs_hidden, attn_softmax)
        outputs = tf.reduce_sum(weighted_projection, axis=1)

    with tf.variable_scope('layer_gather'):

        tf_padded_final = tf.zeros(shape=[1,max_sent_seq_len,output_size * 2])
        #tf_padded_final = tf.zeros(shape=[1,1,output_size * 2])
        sentence_batch_len = tf.placeholder(shape=[None],dtype=tf.int32,name="sentence_batch_len")
        sentence_index_offsets = tf.placeholder(shape=[None,2],dtype=tf.int32,name="sentence_index_offsets")

        sentence_batch_length_2 = tf.placeholder(shape=[None],dtype=tf.int32,name="sentence_batch_len_2")

        i = tf.constant(1)

        # A proud moment =)
        # Used tensorflow conditionals for the first time!!

        # going to try reshape  on individal sentence sizes
        def while_cond (i, tf_padded_final):
            mb = tf.constant(max_sent_seq_len)
            return tf.less_equal(i,mb)

        def body(i,tf_padded_final):

            tf_mask = tf.equal(sentence_batch_length_2,i)
            tf_slice = tf.boolean_mask(outputs,tf_mask,axis=0)

            tf_slice_reshape = tf.reshape(tf_slice,shape=[-1,i,tf_slice.get_shape().as_list()[1]])
            pad_len = max_sent_seq_len - i


            tf_slice_padding = [[0,0], [0, pad_len], [0, 0]]
            tf_slice_padded = tf.pad(tf_slice_reshape, tf_slice_padding, 'CONSTANT')
            #tf_slice_padded_3D = tf.expand_dims(tf_slice_padded, axis=0)
            #tf_padded_final = tf.concat([tf_padded_final,tf_slice_padded_3D],axis=0)

            tf_padded_final = tf.concat([tf_padded_final,tf_slice_padded],axis=0)

            i = tf.add(i,1)

            return i, tf_padded_final



        '''
        # This is the old way
        def while_cond (i, tf_padded_final):
            mb = tf.constant(max_sent_seq_len)
            return tf.less(i,mb)

        def body(i,tf_padded_final):

            #tf.print(i,[i])
            end_idx = sentence_index_offsets[i,1]
            st_idx = sentence_index_offsets[i,0]
            tf_range = tf.range(start=st_idx,limit=end_idx)
            pad_len = max_sent_seq_len - sentence_batch_len[i]

            tf_slice = tf.gather(outputs,tf_range)
            tf_slice_padding = [[0, pad_len], [0, 0]]
            tf_slice_padded = tf.pad(tf_slice, tf_slice_padding, 'CONSTANT')
            tf_slice_padded_3D = tf.expand_dims(tf_slice_padded, axis=0)

            tf_padded_final = tf.concat([tf_padded_final,tf_slice_padded_3D],axis=0)

            i = tf.add(i,1)

            return i, tf_padded_final
            
        '''

        _, tf_padded_final_2 = tf.while_loop(while_cond, body, [i, tf_padded_final],shape_invariants=[i.get_shape(),tf.TensorShape([None,12,output_size_sent * 2])])


    # Give it a haircut
    tf_padded_final_2 = tf_padded_final_2[1:,:]

    with tf.variable_scope('layer_sentence_hidden_states'):

        ((fw_outputs_sent, bw_outputs_sent),
         _) = (
            tf.nn.bidirectional_dynamic_rnn(cell_fw=cell_sent_fw,
                                            cell_bw=cell_sent_bw,
                                            inputs=tf_padded_final_2,
                                            sequence_length=sentence_batch_len,
                                            dtype=tf.float32,
                                            swap_memory=True,
                                            ))
        outputs_hidden_sent = tf.concat((fw_outputs_sent, bw_outputs_sent), 2)

    with tf.variable_scope('layer_sentence_attention'):

        initializer_sent = tf.contrib.layers.xavier_initializer()

        # Big brain #2 (or is this Pinky..?)
        attention_context_vector_sent = tf.get_variable(name='attention_context_vector_sent',
                                                   shape=[output_size_sent * 2],
                                                   initializer=initializer_sent,
                                                   dtype=tf.float32)

        input_projection_sent = tf.contrib.layers.fully_connected(outputs_hidden_sent, output_size_sent * 2,
                                                             activation_fn=tf.nn.relu)
        vector_attn_sent = tf.tensordot(input_projection_sent, attention_context_vector_sent, axes=[[2], [0]], name="vector_attn_sent")
        attn_softmax_sent = tf.map_fn(lambda batch:
                                 sparse_softmax(batch)
                                 , vector_attn_sent, dtype=tf.float32)

        attn_softmax_sent = tf.expand_dims(input=attn_softmax_sent, axis=2, name='attn_softmax_sent')

        weighted_projection_sent = tf.multiply(outputs_hidden_sent, attn_softmax_sent)
        outputs_sent = tf.reduce_sum(weighted_projection_sent, axis=1)

    with tf.variable_scope('layer_classification'):

        wt_init = tf.contrib.layers.xavier_initializer()
        wt = tf.get_variable(name="wt",shape=[output_size_sent * 2,1],initializer=wt_init)
        bias = tf.get_variable(name="bias",shape=[1],initializer=tf.zeros_initializer())

        logits = tf.add(tf.matmul(outputs_sent,wt),bias)
        logits = tf.squeeze(logits)
        probs = tf.sigmoid(logits)

    #return embedding_init, embedding_placeholder, \
    #       inputs, inputs_embed, batch_sequence_lengths,\
    #       vector_attn, attn_softmax, \
    #       weighted_projection, tf_padded_final, outputs_sent, outputs_hidden_sent

    return probs, logits, inputs,batch_sequence_lengths, sentence_batch_len, \
            sentence_index_offsets,  sentence_batch_length_2


def build_loss_optimizer(logits):

    # Create the back propagation and training evaluation machinery in the graph.
    with tf.name_scope('cross_entropy'):
        # Define loss and optimizer
        ground_truth_input = tf.placeholder(
            tf.float32, [None], name='groundtruth_input')

        cross_entropy_mean = tf.nn.sigmoid_cross_entropy_with_logits(
            labels=ground_truth_input, logits=logits)
        learning_rate_input = tf.placeholder(
            tf.float32, [], name='learning_rate_input')

        loss = tf.reduce_mean(cross_entropy_mean, name="cross_entropy_loss")

        #extra_update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)  # For batch normalization ops update
        #with tf.control_dependencies(extra_update_ops):
        train_step = tf.train.AdamOptimizer(
            learning_rate_input).minimize(loss)

        #train_step = tf.train.GradientDescentOptimizer(
        #    learning_rate_input).minimize(loss)

        #train_step = tf.train.AdagradOptimizer(
        #    learning_rate_input).minimize(loss)

        #predicted_indices = tf.argmax(logits, 1, name="predicted_indices")
        predicted_indices = tf.to_int32(tf.greater_equal(logits,0.5))
        confusion_matrix = tf.confusion_matrix(
            ground_truth_input, predicted_indices, num_classes=2, name="confusion_matrix")

    return ground_truth_input, learning_rate_input, train_step, confusion_matrix, cross_entropy_mean, loss



def build_session(train_file, glove_file,mmap_loc):

    num_epochs = 200000
    mini_batch_size = 128
    learning_rate = 0.01

    #validation_batch_size = 1000

    #train_tensorboard_dir = '/home/ubuntu/Desktop/kaggle/kaggle_projects/quora_insincere_qns/tensorboard/train/'
    #valid_tensorboard_dir = '/home/ubuntu/Desktop/kaggle/kaggle_projects/quora_insincere_qns/tensorboard/valid/'

    train_tensorboard_dir = '/home/nitin/Desktop/kaggle_data/all/tensorboard/train/'
    valid_tensorboard_dir = '/home/nitin/Desktop/kaggle_data/all/tensorboard/valid/'


    #chkpoint_dir = '/home/ubuntu/Desktop/kaggle/kaggle_projects/quora_insincere_qns/tensorboard/checkpoint/'
    chkpoint_dir = '/home/nitin/Desktop/kaggle_data/all/tensorboard/checkpoint/'

    if (os.path.exists(train_tensorboard_dir)):
        shutil.rmtree(train_tensorboard_dir)
    os.mkdir(train_tensorboard_dir)

    if (os.path.exists(valid_tensorboard_dir)):
        shutil.rmtree(valid_tensorboard_dir)
    os.mkdir(valid_tensorboard_dir)


    # Build the graph and the optimizer and loss
    with tf.Graph().as_default() as gr:
        final_probs, logits,  inputs, batch_sequence_lengths, sentence_batch_len,\
         sentence_index_offsets, sentence_batch_length_2 = \
            build_graph(cutoff_seq)

        ground_truth_input, learning_rate_input, train_step, confusion_matrix, cross_entropy_mean, loss \
            = build_loss_optimizer(logits=logits)

    X_train, X_dev, glove_dict = get_train_df_glove_dict(train_file, glove_file,mmap_loc)

    print ('X_ men shape')
    print (X_train.shape)

    valid_set_shape = X_dev.shape[0]
    # Open the read mmap
    mmap = np.memmap(mmap_loc, dtype='float32', mode='r', shape=(cutoff_shape + 2, glove_dim))

    with tf.Session(graph=gr,config=tf.ConfigProto(log_device_placement=False)) as sess:

        sess.run(tf.global_variables_initializer())
        saver = tf.train.Saver()

        train_writer = tf.summary.FileWriter(train_tensorboard_dir, sess.graph)
        valid_writer = tf.summary.FileWriter(valid_tensorboard_dir)

        xent_counter = 0

        for i in range(0,num_epochs):

            # Sample mini batch of documents
            #train_sample = X_train.sample(n = mini_batch_size)
            train_sample = X_train
            qn_npy, qn_batch_len,  sentence_len, sentence_batch_train_2 = process_questions(train_sample,glove_dict,mmap)
            y_train = np.asarray(train_sample.loc[:,'target'])


            # Create a matrix with each row as sentence offsets
            # That gets used to rollup the flattened sentences into their documents
            sentence_offsets = np.cumsum(sentence_len)
            sentence_offsets_2 = np.insert(sentence_offsets,0,0,axis=0)
            sentence_offsets_3 = np.delete(sentence_offsets_2,sentence_offsets_2.shape[0] - 1)
            np_offsets_len = np.column_stack([sentence_offsets_3,sentence_offsets])



            prob, _, train_confusion_matrix, train_loss = \
                sess.run([final_probs,train_step,confusion_matrix, loss], feed_dict = {
                    inputs : qn_npy,
                    batch_sequence_lengths : qn_batch_len,
                    sentence_batch_len : sentence_len,
                    sentence_index_offsets : np_offsets_len,
                    learning_rate_input : learning_rate,
                    ground_truth_input : y_train,
                    sentence_batch_length_2 : sentence_batch_train_2
            })

            #print ('Pad2')
            #print (padd_2.shape)
            #print (padd_2[0])
            #print (out[0])
            #print (len(sentence_batch_train_2))

            #print(sentence_batch_train_2)

            print ('Epoch is:' + str(i))
            print ('Training Confusion Matrix')
            print (train_confusion_matrix)
            print ('Train loss')
            print (train_loss)

            true_pos = np.sum(np.diag(train_confusion_matrix))
            all_pos = np.sum(train_confusion_matrix)
            print('Training Accuracy is: ' + str(float(true_pos / all_pos)))
            print('Total data points:' + str(all_pos))

            train_auc = roc_auc_score(y_train,prob,average="weighted")
            print ('Train AUC')
            print (train_auc)


            xent_counter += 1

            loss_train_summary = tf.Summary(
                value=[tf.Summary.Value(tag="loss_train_summary", simple_value=train_loss)])
            train_writer.add_summary(loss_train_summary, xent_counter)

            acc_train_summary = tf.Summary(
                value=[tf.Summary.Value(tag="acc_train_summary", simple_value=float(true_pos / all_pos))])
            train_writer.add_summary(acc_train_summary, xent_counter)

            auc_train_summary = tf.Summary(
                value=[tf.Summary.Value(tag="auc_train_summary", simple_value=train_auc)])
            train_writer.add_summary(auc_train_summary, xent_counter)

            if (i % 10 == 0):

                print('Saving checkpoint for epoch:' + str(i))
                saver.save(sess=sess, save_path=chkpoint_dir + 'quora_insincere_qns.ckpt',
                           global_step=i)

            # Validation machinery
            if (i % 20 == 0):

                valid_conf_matrix = None
                validation_loss = None

                print ('Valid set shape')
                print (valid_set_shape)

                #for j in range(0,valid_set_shape,mini_batch_size):

                    #valid_sample = X_dev[j:j+mini_batch_size]
                    #y_valid = valid_sample.loc[:,'target']

                y_valid = X_dev.loc[:, 'target']

                qn_npy_valid, qn_batch_len_valid, sentence_len_valid, sentence_batch_valid_2 = process_questions(X_dev, glove_dict,mmap)

                sentence_offsets = np.cumsum(sentence_len_valid)
                sentence_offsets_2 = np.insert(sentence_offsets, 0, 0, axis=0)
                sentence_offsets_3 = np.delete(sentence_offsets_2, sentence_offsets_2.shape[0] - 1)
                np_offsets_len = np.column_stack([sentence_offsets_3, sentence_offsets])


                valid_prob, conf_matrix, valid_loss = \
                    sess.run([final_probs,confusion_matrix, loss], feed_dict={
                        inputs: qn_npy_valid,
                        batch_sequence_lengths: qn_batch_len_valid,
                        sentence_batch_len: sentence_len_valid,
                        sentence_index_offsets: np_offsets_len,
                        ground_truth_input: y_valid,
                        sentence_batch_length_2 : sentence_batch_valid_2
                    })

                if valid_conf_matrix is None:
                    valid_conf_matrix = conf_matrix
                    validation_loss = valid_loss
                else:
                    valid_conf_matrix += conf_matrix
                    validation_loss += valid_loss

                print ('Validation Conf matrix')
                print(valid_conf_matrix)
                print ('Validation Loss')
                print (validation_loss)

                true_pos = np.sum(np.diag(valid_conf_matrix))
                all_pos = np.sum(valid_conf_matrix)
                print('Training Accuracy is: ' + str(float(true_pos / all_pos)))
                print('Total data points:' + str(all_pos))

                valid_auc = roc_auc_score(y_valid, valid_prob,average="weighted")
                print('Valid AUC')
                print(valid_auc)

                loss_valid_summary = tf.Summary(
                    value=[tf.Summary.Value(tag="loss_valid_summary", simple_value=validation_loss)])
                valid_writer.add_summary(loss_valid_summary, i / 20)

                acc_valid_summary = tf.Summary(
                    value=[tf.Summary.Value(tag="acc_valid_summary", simple_value=float(true_pos / all_pos))])
                valid_writer.add_summary(acc_valid_summary, i / 20)

                auc_valid_summary = tf.Summary(
                    value=[tf.Summary.Value(tag="auc_valid_summary", simple_value=valid_auc)])
                valid_writer.add_summary(auc_valid_summary, i / 20)


def main():
    glove_file = '/home/ubuntu/Desktop/k_contest/all/glove.840B.300d.txt'
    train_file = '/home/ubuntu/Desktop/k_contest/all/train.csv'
    test_data = '/home/nitin/Desktop/kaggle_data/all/test.csv'

    memmap_loc = '/home/nitin/Desktop/kaggle_data/all/memmap_file_embeddings.npy'
    #memmap_loc = '/home/ubuntu/Desktop/k_contest/all/memmap_file_embeddings.npy'

    glove_file = '/home/nitin/Desktop/kaggle_data/all/embeddings/glove.840B.300d/glove.840B.300d.txt'
    train_file = '/home/nitin/Desktop/kaggle_data/all/train.csv'
    test_data = '/home/nitin/Desktop/kaggle_data/all/test.csv'

    #load_glove_vectors(memmap_loc,glove_file)

    #read_train_test_words(train_data,test_data,glove_vectors_file)

    build_session(train_file,glove_file,memmap_loc)
    #build_session(train_file,glove_file)
    #sampling(train_data)

    #glove_dict, wt = load_glove_vectors(glove_vectors_file)
    #process_questions(df,glove_dict)





main()








