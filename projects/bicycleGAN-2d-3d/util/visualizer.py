import ntpath
import os
import time

import numpy as np
# from scipy.misc import imresize
from PIL import Image
from . import html
from . import util


# save image to the disk
# def save_images(webpage, images, names,image_path, aspect_ratio=1.0, width=256):
def save_images(webpage, images, names, child_dir,image_path, aspect_ratio=1.0, width=256):

    image_dir = webpage.get_image_dir()

    name = ntpath.basename(image_path)

    webpage.add_header(name)
    ims, txts, links = [], [], []

    for label, im_data in zip(names, images):
        # 原图直接保存

        if label=='input' or label=='ground truth':
            im = util.tensor2im(im_data)
        else:
        # 否则，需要分割一下
            im = util.tensor2im_Segment(im_data)
        # image_name = '%s_%s.png' % (name, label)
        # 改为.bmp保存
        # image_name = '%s_%s.bmp' % (name, label)
        image_name = os.path.join(child_dir,'%s_%s.bmp' % (name, label))
        save_path = os.path.join(image_dir, image_name)

        # h, w, _ = im.shape
        h, w= im.shape

        # aspect_ratio=1.0
        if aspect_ratio > 1.0:
            im = np.array(Image.fromarray(im).resize( (h, w * aspect_ratio)))
            # im = imresize(im, (h, int(w * aspect_ratio)), interp='bicubic')
        if aspect_ratio < 1.0:
            im =  np.array(Image.fromarray(im).resize((h / aspect_ratio, w)))
            # im = imresize(im, (int(h / aspect_ratio), w), interp='bicubic')

        util.save_image(im, save_path)

        ims.append(image_name)
        txts.append(label)
        links.append(image_name)
    webpage.add_images(ims, txts, links, width=width)


class Visualizer():
    def __init__(self, opt):
        self.display_id = opt.display_id
        self.use_html = opt.isTrain and not opt.no_html
        self.win_size = opt.display_winsize
        self.name = opt.name
        self.opt = opt
        self.saved = False
        if self.display_id > 0:
            import visdom
            self.ncols = opt.display_ncols
            self.vis = visdom.Visdom(server=opt.display_server, port=opt.display_port)

        if self.use_html:
            self.web_dir = os.path.join(opt.checkpoints_dir, opt.name, 'web')
            self.img_dir = os.path.join(self.web_dir, 'images')
            print('create web directory %s...' % self.web_dir)
            util.mkdirs([self.web_dir, self.img_dir])
        self.log_name = os.path.join(opt.checkpoints_dir, opt.name, 'loss_log.txt')
        with open(self.log_name, "a") as log_file:
            now = time.strftime("%c")
            log_file.write('================ Training Loss (%s) ================\n' % now)

    def reset(self):
        self.saved = False

    # |visuals|: dictionary of images to display or save
    def display_current_results(self, visuals, epoch, save_result):
        if self.display_id > 0:  # show images in the browser
            ncols = self.ncols
            if ncols > 0:
                ncols = min(ncols, len(visuals))
                h, w = next(iter(visuals.values())).shape[:2]
                table_css = """<style>
                        table {border-collapse: separate; border-spacing:4px; white-space:nowrap; text-align:center}
                        table td {width: %dpx; height: %dpx; padding: 4px; outline: 4px solid black}
                        </style>""" % (w, h)
                title = self.name
                label_html = ''
                label_html_row = ''
                images = []
                idx = 0
                for label, image in visuals.items():
                    image_numpy = util.tensor2im(image)
                    # print('------%s image_numpy.dtype--------' % label,image_numpy.dtype)
                    # print('-------%s image_numpy.shape-----------'% label ,image_numpy.shape)
                    label_html_row += '<td>%s</td>' % label
                    # images.append(image_numpy.transpose([2, 0, 1]))   # commented by fjx 20181223
                    images.append(image_numpy)  # 单通道不需要转置
                    idx += 1
                    if idx % ncols == 0:
                        label_html += '<tr>%s</tr>' % label_html_row
                        label_html_row = ''

                # white_image = np.ones_like(image_numpy.transpose([2, 0, 1])) * 255  # commented by fjx 20181223
                white_image = np.ones_like(image_numpy) * 255

                while idx % ncols != 0:
                    images.append(white_image)
                    label_html_row += '<td></td>'
                    idx += 1
                if label_html_row != '':
                    label_html += '<tr>%s</tr>' % label_html_row
                # pane col = image row
                # self.vis.images(images, nrow=ncols, win=self.display_id + 1,padding=2, opts=dict(title=title + ' images'))
                # commented by fjx   这里不知为什么，传入的图像个数大于4就会报错，调试了一下午+一晚上，没有解决。只能注释了。反正对实验结果没有影响。
                label_html = '<table>%s</table>' % label_html
                self.vis.text(table_css + label_html, win=self.display_id + 2,
                              opts=dict(title=title + ' labels'))
            else:
                idx = 1
                for label, image in visuals.items():
                    image_numpy = util.tensor2im(image)
                    # self.vis.image(image_numpy.transpose([2, 0, 1]), opts=dict(title=label),
                    #                win=self.display_id + idx)  # commented by fjx 20181223
                    self.vis.image(image_numpy, opts=dict(title=label),
                                   win=self.display_id + idx)
                    idx += 1

        if self.use_html and (save_result or not self.saved):  # save images to a html file
            self.saved = True
            for label, image in visuals.items():
                image_numpy = util.tensor2im(image)
                img_path = os.path.join(self.img_dir, 'epoch%.3d_%s.png' % (epoch, label))
                util.save_image(image_numpy, img_path)
            # update website
            webpage = html.HTML(self.web_dir, 'Experiment name = %s' % self.name, reflesh=1)
            # n是从epoch到0的序列：如10,9,8,...,1
            for n in range(epoch, 0, -1):
                webpage.add_header('epoch [%d]' % n)
                ims, txts, links = [], [], []

                for label, image_numpy in visuals.items():
                    image_numpy = util.tensor2im(image)
                    img_path = 'epoch%.3d_%s.png' % (n, label)
                    ims.append(img_path)
                    txts.append(label)
                    links.append(img_path)
                webpage.add_images(ims, txts, links, width=self.win_size)
            webpage.save()

    # losses: dictionary of error labels and values
    def plot_current_losses(self, epoch, counter_ratio, opt, losses):
        if not hasattr(self, 'plot_data'):
            self.plot_data = {'X': [], 'Y': [], 'legend': list(losses.keys())}
        self.plot_data['X'].append(epoch + counter_ratio)
        self.plot_data['Y'].append([losses[k] for k in self.plot_data['legend']])
        self.vis.line(
            X=np.stack([np.array(self.plot_data['X'])] * len(self.plot_data['legend']), 1),
            Y=np.array(self.plot_data['Y']),
            opts={
                'title': self.name + ' loss over time',
                'legend': self.plot_data['legend'],
                'xlabel': 'epoch',
                'ylabel': 'loss'},
            win=self.display_id)

    # losses: same format as |losses| of plot_current_losses
    def print_current_losses(self, epoch, i, losses, t, t_data):
        message = '(epoch: %d, iters: %d, time: %.3f, data: %.3f) ' % (epoch, i, t, t_data)
        for k, v in losses.items():
            message += '%s: %.3f ' % (k, v)

        print(message)
        with open(self.log_name, "a") as log_file:
            log_file.write('%s\n' % message)

# import pandas