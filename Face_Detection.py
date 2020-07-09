import os
import time
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader
from LFWDataset import LFWDataset
# Measure the time

# 1. change models
# 2. fc layer change
# 3. lr decreasing, and stop
# 4. Batch size change (bigger)
# ( freeze thge weights)
# 0-1 is because relu!!!! input is possible to rescale -1 to 1, but output would be better to rescale to 0 to 1 because of relu


def split_txt(input_path, ratio = 0.8):

    with open(input_path, "r") as src:
        in_buffer = src.read().split('\n')

        n_split = int(len(in_buffer)*ratio)
        out1_buffer = in_buffer[:n_split]
        out2_buffer = in_buffer[n_split:]

    out1_path = input_path[:-4]+'_0_%d.txt' % (ratio*10)
    with open(out1_path, "w+") as f1:
        for line in out1_buffer:
            f1.write(line + '\n')

    out2_path = input_path[:-4]+'_0_%d.txt' % (round(1-ratio,1)*10)
    with open(out2_path, "w+") as f2:
        for line in out2_buffer:
            f2.write(line + '\n')

    print('\n==> Input file is successfully split by the ratio of '\
          '{}\n\t\t{}\n\t\t{}\n'.format(ratio, out1_path, out2_path))


    return out1_path, out2_path

def visualize_batch():
    # Visualize batch data
    idx, (image_tensor, label_tensor) = next(enumerate(lfw_train_loader))
    print('Image Tensor Shape (N, C, H, W)', image_tensor.shape) # N = Batch size (32)
    print('label Tensor Shape (N, 7, 2)', label_tensor.shape)

    N, C, H, W = image_tensor.shape[0], image_tensor.shape[1], image_tensor.shape[2], image_tensor.shape[3]
    nd_image = (image_tensor.cpu().numpy().reshape(N, C, H, W) + 1) / 2.
    nd_label = label_tensor.cpu().numpy().reshape(N, 7, 2)

    figs, axes = plt.subplots(1, 4)
    for i in range(0, 4):
        axes[i].imshow(nd_image[i].reshape(H, W, C))
        axes[i].scatter(nd_label[i][:, 0], nd_label[i][:, 1], marker='.', c='r')
    plt.show()

# ------------------------------------------------------------------------------------------------------------
# https://github.com/pytorch/vision/blob/master/torchvision/models/alexnet.py
# https://csil-git1.cs.surrey.sfu.ca/luweiy/Tango/blob/master/core_dl/base_net.py
import numpy as np
import torch
from torch.autograd import Variable
from torch.optim.lr_scheduler import MultiStepLR
from LFWNet import LFWNet

torch.set_default_tensor_type('torch.cuda.FloatTensor')


def trainNet(lfw_train_loader, learning_rate=0.0000001, max_epoch=1):
    train_start = time.time()

    # Define the Net
    net = LFWNet()
    # Load the pretrained parameters from Alexnet
    net.load_state(torch.load('alexnet_parameters.pth'))
    # Set the parameter defined in the net to GPU
    net.cuda()

    # Define the loss
    criterion = torch.nn.MSELoss()

    # Define Optimizer
    optimizer = torch.optim.Adam(net.parameters(), lr=learning_rate)
    scheduler = MultiStepLR(optimizer, milestones=[5,10], gamma=0.1)

    train_losses = []
    valid_losses = []
    itr = 0
    for epoch_idx in range(0, max_epoch):

        # decrease lr
        scheduler.step()
        print('\n\n===> lr: %.10f' % float(scheduler.get_lr()[0]))
        # stop learning if validation loss is going up

        # print(len(valid_losses))

        # iterate the mini-batches:
        for train_batch_idx, (train_img, train_label) in enumerate(lfw_train_loader):
            # Switch to train model
            net.train()

            # update the parameter gradients as zero
            optimizer.zero_grad()

            # Forward
            train_img = Variable(train_img.cuda())
            train_out = net.forward(train_img)

            # compute the loss
            train_label = Variable(train_label.cuda())
            train_loss = criterion(train_out, train_label)

            # Do the backward to compute the gradient flow
            train_loss.backward()

            # Update the parameters
            optimizer.step()

            train_losses.append((itr, train_loss.item()))
            itr += 1

            #Show intermediate results
            if train_batch_idx % 100 == 0:
                # print(train_img.shape) # N, C, H, W
                # image = train_img[0, :, :, :].cpu().numpy().astype(np.float32).transpose()  # c , h, w -> h, w, c
                # landmarks = train_label[0, :].cpu().numpy().astype(np.float32).reshape((7, 2))
                # pred = train_out.detach()[0, :].cpu().numpy().astype(np.float32).reshape((7, 2))
                # landmarks = landmarks * 225
                # pred = pred * 225
                # plt.figure()
                # plt.imshow((image+1)/2)
                # plt.scatter(landmarks[:, 0], landmarks[:, 1], marker='.', c='r')
                # plt.scatter(pred[:, 0], pred[:, 1], marker='.', c='b')
                # plt.show()
                print('[Train]epoch: %d itr: %d Loss: %.4f' % (epoch_idx, itr, train_loss.item()))

            # validaton
            if train_batch_idx % 200 == 0:
                net.eval() # Evaluation mode
                valid_losses_subset = []  # collect the validation losses for avg.

                for valid_itr, (valid_image, valid_label) in enumerate(lfw_valid_loader):
                    valid_image = Variable(valid_image.cuda())
                    valid_label = Variable(valid_label.cuda())

                    # Forward and compute loss
                    valid_out = net.forward(valid_image)
                    valid_loss = criterion(valid_out, valid_label)
                    valid_losses_subset.append(valid_loss.item())

                    valid_itr += 1
                    if valid_itr > 5:
                        break

                # avg. valid loss
                avg_valid_loss = np.mean(np.asarray(valid_losses_subset))
                valid_losses.append((itr, avg_valid_loss))
                print('[Valid]epoch: %d iter: %d loss: %.4f ' % (epoch_idx, itr, avg_valid_loss))

    results_file_name = 'lfw__ep_{}_itr_{}_lr_{}'.format(max_epoch, itr, learning_rate)

    train_losses = np.asarray(train_losses)
    plt.plot(train_losses[:, 0], train_losses[:, 1])

    valid_losses = np.asarray(valid_losses)
    plt.plot(valid_losses[:, 0], valid_losses[:, 1])

    plt.savefig(lfw_lab_results_dir+results_file_name+'__loss_%.2f.png' % (train_losses[-1][1]*100))
    # large batchsize makes more stable loss curve

    # Save the trained network

    net_state = net.state_dict()  # serialize the instance
    results_path = os.path.join(lfw_lab_results_dir, results_file_name+'__model.pth')
    torch.save(net_state, results_path)

    # Measure the time
    train_end = time.time()
    m, s = divmod(train_end - train_start, 60)
    h, m = divmod(m, 60)
    results_log = '---------------------------------------------\n'
    results_log += '\tStart learning rate: %.8f\n' % learning_rate
    results_log += '\tEnd learning rate: %.8f\n' % float(scheduler.get_lr()[0])
    results_log += '\tTotal time to train model: %d:%02d:%02d \n' % (h, m, s)
    results_log += '\tThe last loss of training: %.4f\n' % train_losses[-1][1]
    results_log += '\tThe last loss of validation: %.4f\n' % valid_losses[-1][1]

    return results_path, results_log

def testNet(results_path):

    # Load the save model and deploy
    test_net = LFWNet()

    test_net_state = torch.load(os.path.join(lfw_lab_dir, results_path))
    test_net.load_state_dict(test_net_state)
    test_net.eval()

    radius_range = np.arange(0, 50, 0.1)
    acc = np.zeros((len(radius_range), 7))
    iter_limit = len(lfw_test_dataset)
    for test_item_idx in range(0, iter_limit):
        # test_item_idx = random.choice(range(0, len(lfw_test_dataset)))
        test_image_tensor, test_label_tensor = lfw_test_dataset[test_item_idx]

        # run Forward
        pred = test_net.forward(test_image_tensor.view((1, 3, 225, 225)).cuda()) # N C H W

        # Show the result
        test_image = test_image_tensor.cpu().numpy().transpose() # H, W, C
        # print(test_image.shape)
        test_pred = pred.detach().cpu().numpy().reshape((7, 2))
        test_label = test_label_tensor.cpu().numpy().reshape((7, 2))

        test_image = ((test_image + 1) / 2. * 255.).astype(int)
        test_pred = test_pred * 225
        test_label = test_label * 225
        #
        # plt.imshow(test_image)
        # plt.scatter(test_pred[:, 0], test_pred[:, 1], marker='.', c='b')
        # plt.scatter(test_label[:, 0], test_label[:, 1], marker='.', c='r')
        #
        # plt.show()

        # Accuracy
        for idx, radius in zip(range(0, len(radius_range)), radius_range):
            for i in range(0, 7):
                distance = np.linalg.norm(test_pred[i]-test_label[i])
                if distance <= radius:
                    acc[idx][i] += 1

    accuracy = min([ r if acc > 90 else 1000 for r , acc in zip(radius_range, np.average(acc, axis=1) / iter_limit * 100)])
    # acc_arr = np.average(acc, axis=1) / iter_limit * 100
    acc_arr = acc / iter_limit * 100

    plt.plot(radius_range, acc_arr)
    plt.legend(['canthus_rr', 'canthus_rl', 'canthus_lr', 'canthus_ll', 'mouse_corner_r', 'mouse_corner_l', 'nose'])
    plt.grid()
    # plt.savefig(results_path[:-10] + '__accuracy_{}.png'.format(accuracy))
    plt.show()

if __name__ == "__main__":
    # Set the file path
    lfw_lab_dir = "./"
    lfw_image_dir = os.path.join(lfw_lab_dir, "lfw/")
    lfw_test_path = os.path.join(lfw_lab_dir, "LFW_annotation_test.txt")
    lfw_train_path, lfw_valid_path = split_txt(os.path.join(lfw_lab_dir, "LFW_annotation_train.txt"), ratio=0.8)
    lfw_lab_results_dir = "./results/" # for the results

    # Define Train Dataset/loader
    lfw_train_dataset = LFWDataset(lfw_image_dir, lfw_train_path, n_augmented=3) # n_augmented=3
    lfw_train_loader = DataLoader(lfw_train_dataset, batch_size=32, shuffle=True, num_workers=6)
    print('Total lfw training items: ', len(lfw_train_dataset))
    print('Total lfw Training Batches size in one epoch: ', len(lfw_train_loader))

    # Define Valid Dataset/loader
    lfw_valid_dataset = LFWDataset(lfw_image_dir, lfw_valid_path)
    lfw_valid_loader = DataLoader(lfw_valid_dataset, batch_size=32, shuffle=True, num_workers=6)
    print('Total lfw validating items: ', len(lfw_valid_dataset))
    print('Total lfw validating Batches size in one epoch: ', len(lfw_valid_loader))

    # Define Test Dataset/loader
    lfw_test_dataset = LFWDataset(lfw_image_dir, lfw_test_path)
    print('Total lfw testing items: ', len(lfw_test_dataset))

    # Train
    results_model_path, results_log = trainNet(lfw_train_loader, learning_rate=0.000005, max_epoch=20)
    # testNet(results_model_path)
    print(results_log)
    print(results_model_path)

    # Test
    testNet("results/"+"lfw__ep_20_itr_15020_lr_5e-06__model.pth")
